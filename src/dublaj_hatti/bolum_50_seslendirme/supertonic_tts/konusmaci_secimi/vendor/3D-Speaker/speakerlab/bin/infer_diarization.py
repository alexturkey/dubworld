# Copyright 3D-Speaker (https://github.com/alibaba-damo-academy/3D-Speaker). All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)

"""
This is a speaker diarization inference script based on pretrained models.
This project-owned copy exposes only the audio-only library path used by the dubbing pipeline.
"""

import os
import sys
import warnings
from time import perf_counter

import numpy as np
import json

import torch

try:
    from speakerlab.utils.config import Config
except ImportError:
    sys.path.append('%s/../..'%os.path.dirname(os.path.abspath(__file__)))
    from speakerlab.utils.config import Config

from speakerlab.utils.builder import build
from speakerlab.utils.utils import download_model_from_modelscope, circle_pad
from speakerlab.utils.fileio import load_audio

os.environ['MODELSCOPE_LOG_LEVEL'] = '40'
warnings.filterwarnings("ignore")



def _timing_started(progress_callback, stage):
    if progress_callback is not None:
        progress_callback(stage + '_started')
    return perf_counter()


def _timing_completed(progress_callback, stage, started, **details):
    if progress_callback is not None:
        progress_callback(stage + '_completed', elapsed_seconds=round(perf_counter() - started, 6), **details)


def get_speaker_embedding_model(device:torch.device = None, cache_dir:str = None, progress_callback=None):
    conf = {
        'model_id': 'iic/speech_campplus_sv_zh_en_16k-common_advanced',
        'revision': 'v1.0.0',
        'model_ckpt': 'campplus_cn_en_common.pt',
        'embedding_model': {
            'obj': 'speakerlab.models.campplus.DTDNN.CAMPPlus',
            'args': {
                'feat_dim': 80,
                'embedding_size': 192,
            },
        },
        'feature_extractor': {
            'obj': 'speakerlab.process.processor.FBank',
            'args': {
                'n_mels': 80,
                'sample_rate': 16000,
                'mean_nor': True,
                },
        }
    }

    cache_dir = download_model_from_modelscope(conf['model_id'], conf['revision'], cache_dir)
    pretrained_model_path = os.path.join(cache_dir, conf['model_ckpt'])
    config = Config(conf)
    started = _timing_started(progress_callback, 'fbank_object_construction')
    feature_extractor = build('feature_extractor', config)
    _timing_completed(progress_callback, 'fbank_object_construction', started)
    started = _timing_started(progress_callback, 'campplus_object_construction')
    embedding_model = build('embedding_model', config)
    _timing_completed(progress_callback, 'campplus_object_construction', started)

    started = _timing_started(progress_callback, 'campplus_checkpoint_load')
    pretrained_state = torch.load(pretrained_model_path, map_location='cpu', weights_only=True)
    embedding_model.load_state_dict(pretrained_state)
    embedding_model.eval()
    _timing_completed(progress_callback, 'campplus_checkpoint_load', started, checkpoint='campplus_cn_en_common.pt')
    if device is not None:
        started = _timing_started(progress_callback, 'campplus_gpu_transfer')
        embedding_model.to(device)
        if device.type == 'cuda':
            torch.cuda.synchronize(device)
        _timing_completed(progress_callback, 'campplus_gpu_transfer', started, device=str(device))
    return embedding_model,  feature_extractor

def get_cluster_backend(progress_callback=None):
    conf = {
        'cluster':{
            'obj': 'speakerlab.process.cluster.CommonClustering',
            'args':{
                'cluster_type': 'spectral',
                'mer_cos': 0.8,
                'min_num_spks': 1,
                'max_num_spks': 15,
                'min_cluster_size': 4,
                'oracle_num': None,
                'pval': 0.012,
            }
        }
    }
    config = Config(conf)
    started = _timing_started(progress_callback, 'clustering_object_construction')
    cluster = build('cluster', config)
    _timing_completed(progress_callback, 'clustering_object_construction', started)
    return cluster

# Project change (2026-10-24): the upstream FSMN VAD runs through modelscope -> funasr, and funasr hard-depends on
# kaldiio, whose license (NTT evaluation-only) forbids redistribution. Voice activity detection therefore uses
# Silero VAD v6 (MIT) as shipped inside faster-whisper (a core dependency), so no extra model download is needed.
SILERO_VAD_OPTIONS = {
    'threshold': 0.5,
    'min_speech_duration_ms': 250,
    'min_silence_duration_ms': 100,
    'speech_pad_ms': 30,
}


class SileroVad:
    """Callable VAD: 16 kHz mono float waveform -> [[start_s, end_s], ...]."""

    sample_rate = 16000

    def __init__(self):
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        self._options = VadOptions(**SILERO_VAD_OPTIONS)
        self._get_speech_timestamps = get_speech_timestamps

    def __call__(self, wav):
        if isinstance(wav, torch.Tensor):
            wav = wav.detach().cpu().numpy()
        audio = np.asarray(wav, dtype=np.float32).reshape(-1)
        stamps = self._get_speech_timestamps(audio, self._options, sampling_rate=self.sample_rate)
        return [[item['start'] / self.sample_rate, item['end'] / self.sample_rate] for item in stamps]


def get_voice_activity_detection_model(device: torch.device=None, cache_dir:str = None, progress_callback=None):
    started = _timing_started(progress_callback, 'silero_vad_construction')
    vad_model = SileroVad()
    _timing_completed(progress_callback, 'silero_vad_construction', started, device='cpu')
    return vad_model


class Diarization3Dspeaker():
    """
    This class is designed to handle the speaker diarization process, 
    which involves identifying and segmenting audio by speaker identities. 
    Args:
        device (str, default=None): The device on which models will run. 
        speaker_num (int, default=None): Specify number of speakers.
        model_cache_dir (str, default=None): If specified, the pretrained model will be downloaded 
            to this directory; only pretrained from modelscope are supported (CAM++; VAD is Silero, see above).
    Usage:
        diarization_pipeline = Diarization3Dspeaker(device)
        output = diarization_pipeline(input_audio) # input_audio can be a path to a WAV file, a NumPy array, or a PyTorch tensor
        print(output) # output: [[1.1, 2.2, 0], [3.1, 4.1, 1], ..., [st_n, ed_n, speaker_id]]
        diarization_pipeline.save_diar_output('audio.rttm') # or audio.json
    """
    def __init__(self, device=None, speaker_num=None, model_cache_dir=None, progress_callback=None):
        self.device = self.normalize_device(device)
        self.embedding_model, self.feature_extractor = get_speaker_embedding_model(
            self.device,
            model_cache_dir,
            progress_callback,
        )
        self.vad_model = get_voice_activity_detection_model(self.device, model_cache_dir, progress_callback)
        self.cluster = get_cluster_backend(progress_callback)
        
        self.batchsize = 64
        self.fs = self.feature_extractor.sample_rate
        self.output_field_labels = None
        self.speaker_num = speaker_num

    def __call__(self, wav, wav_fs=None, speaker_num=None):
        wav_data = load_audio(wav, wav_fs, self.fs)

        # stage 1-1: do vad
        vad_time = self.do_vad(wav_data)
        # stage 2: prepare subseg
        chunks = [c for (st, ed) in vad_time for c in self.chunk(st, ed)]

        # stage 3: extract embeddings
        embeddings = self.do_emb_extraction(chunks, wav_data)

        # stage 4: clustering
        speaker_num, output_field_labels = self.do_clustering(chunks, embeddings, speaker_num)

        self.output_field_labels = output_field_labels
        return output_field_labels

    def do_vad(self, wav):
        # wav: [1, T]
        if self.fs != SileroVad.sample_rate:
            raise ValueError('Silero VAD expects 16 kHz audio, got %s' % self.fs)
        return self.vad_model(wav[0])

    def chunk(self, st, ed, dur=1.5, step=0.75):
        chunks = []
        subseg_st = st
        while subseg_st + dur < ed + step:
            subseg_ed = min(subseg_st + dur, ed)
            chunks.append([subseg_st, subseg_ed])
            subseg_st += step
        return chunks

    def do_emb_extraction(self, chunks, wav):
        # chunks: [[st1, ed1]...]
        # wav: [1, T]
        wavs = [wav[0, int(st*self.fs):int(ed*self.fs)] for st, ed in chunks]
        max_len = max([x.shape[0] for x in wavs])
        wavs = [circle_pad(x, max_len) for x in wavs]
        wavs = torch.stack(wavs).unsqueeze(1)

        embeddings = []
        batch_st = 0
        with torch.no_grad():
            while batch_st < len(chunks):
                wavs_batch = wavs[batch_st: batch_st+self.batchsize].to(self.device)
                feats_batch = torch.vmap(self.feature_extractor)(wavs_batch)
                embeddings_batch = self.embedding_model(feats_batch).cpu()
                embeddings.append(embeddings_batch)
                batch_st += self.batchsize
        embeddings = torch.cat(embeddings, dim=0).numpy()
        return embeddings

    def do_clustering(self, chunks, embeddings, speaker_num=None):
        cluster_labels = self.cluster(
            embeddings, 
            speaker_num = speaker_num if speaker_num is not None else self.speaker_num
        )
        speaker_num = cluster_labels.max()+1
        output_field_labels = [[i[0], i[1], int(j)] for i, j in zip(chunks, cluster_labels)]
        output_field_labels = compressed_seg(output_field_labels)
        return speaker_num, output_field_labels

    def save_diar_output(self, out_file, wav_id=None, output_field_labels=None):
        if output_field_labels is None and self.output_field_labels is None:
            raise ValueError('No results can be saved.')
        if output_field_labels is None:
            output_field_labels = self.output_field_labels

        wav_id = 'default' if wav_id is None else wav_id
        if out_file.endswith('rttm'):
            line_str ="SPEAKER {} 0 {:.3f} {:.3f} <NA> <NA> {:d} <NA> <NA>\n"
            with open(out_file, 'w') as f:
                for seg in output_field_labels:
                    seg_st, seg_ed, cluster_id = seg
                    f.write(line_str.format(wav_id, seg_st, seg_ed-seg_st, cluster_id))
        elif out_file.endswith('json'):
            out_json = {}
            for seg in output_field_labels:
                seg_st, seg_ed, cluster_id = seg
                item = {
                    'start': seg_st,
                    'stop': seg_ed,
                    'speaker': cluster_id,
                }
                segid = wav_id+'_'+str(round(seg_st, 3))+\
                    '_'+str(round(seg_ed, 3))
                out_json[segid] = item
            with open(out_file, mode='w') as f:
                json.dump(out_json, f, indent=2)
        else:
            raise ValueError('The supported output file formats are currently limited to RTTM and JSON.')

    def normalize_device(self, device=None):
        if device is None:
            device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        elif isinstance(device, str):
            device = torch.device(device)
        else:
            assert isinstance(device, torch.device)
        return device

def compressed_seg(seg_list):
    new_seg_list = []
    for i, seg in enumerate(seg_list):
        seg_st, seg_ed, cluster_id = seg
        if i == 0:
            new_seg_list.append([seg_st, seg_ed, cluster_id])
        elif cluster_id == new_seg_list[-1][2]:
            if seg_st > new_seg_list[-1][1]:
                new_seg_list.append([seg_st, seg_ed, cluster_id])
            else:
                new_seg_list[-1][1] = seg_ed
        else:
            if seg_st < new_seg_list[-1][1]:
                p = (new_seg_list[-1][1]+seg_st) / 2
                new_seg_list[-1][1] = p
                seg_st = p
            new_seg_list.append([seg_st, seg_ed, cluster_id])
    return new_seg_list
