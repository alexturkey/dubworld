from collections.abc import Mapping
from pathlib import Path
import shutil

import soundfile as sf


class WavAudioFiles(Mapping):
    def __init__(self, paths, sample_rate):
        self.paths = {int(index): Path(path).resolve() for index, path in paths.items()}
        self.sample_rate = int(sample_rate)
        self.headers = {}
        for index, path in self.paths.items():
            info = sf.info(str(path))
            if info.samplerate != self.sample_rate or info.channels != 1:
                raise ValueError(f"Invalid segment audio format: {index} ({path})")
            self.headers[index] = info

    @classmethod
    def from_relative_paths(cls, directory, paths, sample_rate):
        root = Path(directory).resolve()
        resolved = {}
        for index, relative_path in paths.items():
            path = (root / relative_path).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Segment audio path escapes checkpoint directory")
            if int(index) in resolved:
                raise ValueError("Duplicate segment audio index")
            resolved[int(index)] = path
        return cls(resolved, sample_rate)

    @classmethod
    def from_directory(cls, directory, sample_rate):
        root = Path(directory)
        if not root.is_dir():
            raise FileNotFoundError(root)
        paths = {}
        for path in sorted(root.glob("segment_*.wav")):
            index = int(path.stem.removeprefix("segment_"))
            if index in paths:
                raise ValueError("Duplicate segment audio index")
            paths[index] = path
        return cls(paths, sample_rate)

    def __len__(self):
        return len(self.paths)

    def __iter__(self):
        return iter(self.paths)

    def __contains__(self, index):
        return index in self.paths

    def __getitem__(self, index):
        audio, sample_rate = sf.read(str(self.paths[index]), dtype="float32")
        if sample_rate != self.sample_rate or audio.ndim != 1 or len(audio) != self.headers[index].frames:
            raise ValueError(f"Segment audio changed after validation: {index}")
        return audio


def audio_sample_count(audios, index):
    if isinstance(audios, WavAudioFiles):
        return audios.headers[index].frames if index in audios else None
    audio = audios.get(index)
    return len(audio) if audio is not None else None


def write_segment_audio_files(audios, directory, sample_rate, subtype):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if isinstance(audios, WavAudioFiles):
        if int(sample_rate) != audios.sample_rate:
            raise ValueError("Segment audio sample rate mismatch")
        for index, source in audios.paths.items():
            destination = directory / f"segment_{index}.wav"
            if audios.headers[index].subtype == subtype:
                if source != destination.resolve():
                    shutil.copyfile(source, destination)
            else:
                if source == destination.resolve():
                    raise ValueError("Cannot convert segment audio in place")
                with sf.SoundFile(str(source)) as reader, sf.SoundFile(
                    str(destination), mode="w", samplerate=sample_rate, channels=1, subtype=subtype,
                ) as writer:
                    for block in reader.blocks(blocksize=65536, dtype="float32"):
                        writer.write(block)
        return
    for index, audio in audios.items():
        sf.write(str(directory / f"segment_{index}.wav"), audio, sample_rate, subtype=subtype)
