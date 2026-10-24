import bisect
import hashlib
import json
import math
from pathlib import Path

from PIL import ImageFont


PROFILE_PATH = Path(__file__).with_name('rollup_profile.json')


def validate_profile(profile):
    required = {'schema_version', 'width_ratio', 'row_count', 'font_size', 'frame_height', 'spacing_ratio', 'horizontal_padding', 'bottom_margin', 'scroll_seconds', 'pause_seconds', 'tail_seconds', 'minimum_font_size'}
    if not isinstance(profile, dict) or set(profile) != required or profile['schema_version'] != 1:
        raise ValueError('Invalid rollup profile schema')
    result = dict(profile)
    for key in required - {'frame_height'}:
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'Invalid rollup profile value: {key}')
    if result['frame_height'] is not None and (isinstance(result['frame_height'], bool) or not isinstance(result['frame_height'], (int, float)) or not math.isfinite(result['frame_height']) or result['frame_height'] <= 0):
        raise ValueError('Invalid frame height')
    if not 0 < result['width_ratio'] <= .95 or type(result['row_count']) is not int or not 1 <= result['row_count'] <= 8:
        raise ValueError('Invalid frame geometry')
    if not 16 <= result['minimum_font_size'] <= result['font_size'] <= 200 or not .9 <= result['spacing_ratio'] <= 2:
        raise ValueError('Invalid font geometry')
    if result['horizontal_padding'] < 0 or result['bottom_margin'] < 0 or not 0 < result['scroll_seconds'] <= 2 or result['pause_seconds'] < 0 or not 0 <= result['tail_seconds'] <= 5:
        raise ValueError('Invalid spacing or timing')
    return result


def load_profile():
    return validate_profile(json.loads(PROFILE_PATH.read_text(encoding='utf-8')))


def rollup_contract_inputs():
    profile = load_profile()
    return {'rollup_profile': profile, 'rollup_renderer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rollup_font_sha256': hashlib.sha256(Path(ImageFont.truetype('arial.ttf', 62).path).read_bytes()).hexdigest()}


def group_words(words, width, font, pause_seconds=1.0):
    lines = []
    current = []
    for i, word in enumerate(words):
        text = str(word['word']).strip()
        if not text or not all(math.isfinite(float(word[k])) for k in ('start', 'end')):
            raise ValueError('Invalid word')
        if word['end'] <= word['start'] or word['start'] < 0:
            raise ValueError('Invalid word interval')
        if i and word['start'] < words[i - 1]['start']:
            raise ValueError('Non-increasing word starts')
        if font.getlength(text) > width:
            raise ValueError('Single word exceeds width; explicit layout adjustment required')
        joined = ' '.join([w['word'] for w in current] + [text])
        pause = current and word['start'] - current[-1]['end'] > pause_seconds
        if current and (font.getlength(joined) > width or pause):
            lines.append(current)
            current = []
        current.append(dict(word, word=text, input_index=i))
    if current:
        lines.append(current)
    return lines


def ass_time(seconds):
    ticks = max(0, round(seconds * 100))
    return f'{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}'


def ass_escape(text):
    return text.replace('\\', '\\u005c').replace('{', '｛').replace('}', '｝').replace('\n', ' ')


def build_ass(words, width, height, duration, profile=None):
    profile = validate_profile(profile) if profile is not None else load_profile()
    width_ratio = profile['width_ratio']
    row_count = profile['row_count']
    frame_height = profile['frame_height']
    if not words or width <= 0 or height <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid subtitle input')
    if not 0 < width_ratio <= .95 or not isinstance(row_count, int) or not 1 <= row_count <= 8:
        raise ValueError('Invalid frame width or row count')
    spacing_ratio = profile['spacing_ratio']
    frame_height = frame_height if frame_height is not None else row_count * profile['font_size'] * spacing_ratio
    if not math.isfinite(frame_height) or frame_height <= 0 or frame_height > height - 2 * profile['bottom_margin']:
        raise ValueError('Invalid frame height')
    font_size = min(int(profile['font_size']), math.floor(frame_height / row_count / spacing_ratio + 1e-8))
    container_width = round(width * width_ratio)
    while font_size >= profile['minimum_font_size']:
        measure_font_size = round(font_size * 55 / 62)
        font = ImageFont.truetype('arial.ttf', measure_font_size)
        if all(font.getlength(str(w['word']).strip()) <= container_width - 2 * profile['horizontal_padding'] for w in words):
            break
        font_size -= 1
    if font_size < profile['minimum_font_size']:
        raise ValueError('Frame cannot fit words at minimum readable font size')
    container_left = (width - container_width) // 2
    pad = profile['horizontal_padding']
    left = container_left + pad
    max_width = container_width - 2 * pad
    line_height = spacing_ratio * font_size
    vertical_padding = (line_height - font_size) / 2
    bottom_y = height - profile['bottom_margin'] - line_height
    clip_top = round(bottom_y - (row_count - 1) * line_height)
    clip_bottom = round(bottom_y + line_height)
    lines = group_words(words, max_width, font, profile['pause_seconds'])
    starts = [line[0]['start'] for line in lines]
    scroll_durations = [0.0] + [min(profile['scroll_seconds'], max(.01, starts[k + 1] - starts[k])) if k + 1 < len(lines) else profile['scroll_seconds'] for k in range(1, len(lines))]
    points = {w['start'] for w in words}
    points.update(starts[k] + scroll_durations[k] for k in range(1, len(lines)))
    last_end = min(duration, words[-1]['end'] + profile['tail_seconds'])
    points.add(last_end)
    points = sorted(p for p in points if p <= last_end)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Text,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Box,Arial,10,&H60000000,&H60000000,&H60000000,&H60000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    container_drawing = f'm 0 0 l {container_width} 0 l {container_width} {row_count*line_height} l 0 {row_count*line_height}'
    events = [f'Dialogue: 0,{ass_time(words[0]["start"])},{ass_time(last_end)},Box,,0,0,0,,{{\\an7\\pos({container_left},{clip_top})\\p1}}{container_drawing}{{\\p0}}']
    states = []
    def offset_at(t, k):
        if k == 0:
            return 0.0
        progress = min(1., max(0., (t - starts[k]) / scroll_durations[k]))
        return k - 1 + progress
    for begin, end in zip(points, points[1:]):
        if ass_time(begin) == ass_time(end):
            continue
        k = bisect.bisect_right(starts, begin + 1e-7) - 1
        if k < 0:
            continue
        for line_index in range(max(0, k - row_count), k + 1):
            visible = [w for w in lines[line_index] if w['start'] <= begin + 1e-7]
            if not visible:
                continue
            y0 = bottom_y + (line_index - offset_at(begin, k)) * line_height
            y1 = bottom_y + (line_index - offset_at(end, k)) * line_height
            if max(y0, y1) + line_height <= clip_top:
                continue
            text = ' '.join(w['word'] for w in visible)
            box_width = math.ceil(font.getlength(text)) + 2 * pad
            clip = f'\\clip({left-pad},{clip_top},{left+max_width+pad},{clip_bottom})'
            text_y0, text_y1 = y0 + vertical_padding, y1 + vertical_padding
            move_text = f'\\move({left},{text_y0:.2f},{left},{text_y1:.2f})' if abs(y0-y1) > .001 else f'\\pos({left},{text_y0:.2f})'
            events.append(f'Dialogue: 1,{ass_time(begin)},{ass_time(end)},Text,,0,0,0,,{{\\an7{move_text}{clip}}}{ass_escape(text)}')
            states.append({'start': begin, 'end': end, 'line_index': line_index, 'text': text, 'y0': y0, 'y1': y1, 'text_y0': text_y0, 'text_y1': text_y1, 'width': box_width})
    report = {'word_count': len(words), 'line_count': len(lines), 'ass_event_count': len(events), 'font_size': font_size, 'left': left, 'max_text_width': max_width, 'line_height': line_height, 'scroll_seconds': profile['scroll_seconds'], 'clip': [left-pad, clip_top, left+max_width+pad, clip_bottom], 'max_measured_width': max(font.getlength(' '.join(w['word'] for w in line)) for line in lines), 'word_coverage': [w['input_index'] for line in lines for w in line], 'line_starts': starts, 'states': states}
    report.update({'container_width': container_width, 'container_height': line_height*row_count, 'row_count': row_count, 'requested_frame_height': frame_height, 'width_ratio': width_ratio, 'container_left': container_left, 'horizontal_padding': pad, 'vertical_padding': vertical_padding, 'selected_option': 1, 'reference_line_height': 58.6, 'bottom_margin': profile['bottom_margin'], 'main_font_size': 72, 'font_ratio': font_size/72, 'layout': 'configurable_equal_rows'})
    return header + '\n'.join(events) + '\n', report
