
SUPERTONIC_FLOW_MODE_DEFAULT = 'single_pass_2'
SUPERTONIC_FLOW_MODES = {
    'single_pass_10': {
        'label': 'Tek Gecis - 10 aday, repair yok',
        'candidate_count': 10,
        'max_repair_rounds': 0,
        'repair_enabled': False },
    'single_pass_2': {
        'label': 'Tek Gecis - 2 aday, repair yok',
        'candidate_count': 2,
        'max_repair_rounds': 0,
        'repair_enabled': False },
    'single_pass_1': {
        'label': 'Dogal Turkce - 1 aday, repair yok',
        'candidate_count': 1,
        'max_repair_rounds': 0,
        'repair_enabled': False,
        'translation_group_size': 35,
        'translation_prompt_mode': 'supertonic_single_pass_1_natural' },
    'natural_blocks_1': {
        'label': 'Dogal Anlam Bloklari - 1 aday, repair yok',
        'candidate_count': 1,
        'max_repair_rounds': 0,
        'repair_enabled': False,
        'translation_group_size': 35,
        'translation_prompt_mode': 'supertonic_natural_blocks_1' },
    'repair_3_light': {
        'label': 'Repair 3 Light - 2 aday, en fazla 3 repair',
        'candidate_count': 2,
        'max_repair_rounds': 3,
        'repair_enabled': True,
        'translation_group_size': 35,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_2_initial_1_repair_2': {
        'label': "Repair 2 - İlk tur 1'er aday, repairlerde 2'şer aday",
        'candidate_count': 1,
        'initial_candidate_count': 1,
        'repair_candidate_count': 2,
        'max_repair_rounds': 2,
        'repair_enabled': True,
        'translation_group_size': 35,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_1': {
        'label': 'Repair 1 - 7 aday, en fazla 1 repair',
        'candidate_count': 7,
        'max_repair_rounds': 1,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_2': {
        'label': 'Repair 2 - 7 aday, en fazla 2 repair',
        'candidate_count': 7,
        'max_repair_rounds': 2,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_3': {
        'label': 'Repair 3 - 7 aday, en fazla 3 repair',
        'candidate_count': 7,
        'max_repair_rounds': 3,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_4': {
        'label': 'Repair 4 - 7 aday, en fazla 4 repair',
        'candidate_count': 7,
        'max_repair_rounds': 4,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_5': {
        'label': 'Repair 5 - 7 aday, en fazla 5 repair',
        'candidate_count': 7,
        'max_repair_rounds': 5,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_6': {
        'label': 'Repair 6 - 7 aday, en fazla 6 repair',
        'candidate_count': 7,
        'max_repair_rounds': 6,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' },
    'repair_7': {
        'label': 'Repair 7 - 7 aday, en fazla 7 repair',
        'candidate_count': 7,
        'max_repair_rounds': 7,
        'repair_enabled': True,
        'translation_group_size': 10,
        'translation_prompt_mode': 'supertonic_whole_chain_candidates' } }

def normalize_supertonic_flow_mode(mode = None):
    if not mode:
        return SUPERTONIC_FLOW_MODE_DEFAULT
    value = str(mode).strip().lower()
    if value in frozenset({'repair', '', 'standard', 'default'}):
        return SUPERTONIC_FLOW_MODE_DEFAULT
    if value in frozenset({'single_pass_10', 'fast_single_pass', 'single_pass'}):
        return 'single_pass_10'
    if value in frozenset({'single_pass_2', 'single_pass_light'}):
        return 'single_pass_2'
    if value in frozenset({'single_pass_1', 'single_pass_minimal', 'one_candidate_single_pass'}):
        return 'single_pass_1'
    if value in frozenset({'natural_blocks_1', 'natural_blocks', 'natural_flow_1'}):
        return 'natural_blocks_1'
    if value in frozenset({'repair_3_light', 'light_repair_3', 'repair_light_3', 'two_candidate_repair_3'}):
        return 'repair_3_light'
    if value in frozenset({'repair_2_initial_1_repair_2', 'repair_3_initial_1_repair_2', 'initial_1_repair_2', 'one_candidate_repair_3'}):
        return 'repair_2_initial_1_repair_2'
    if value in SUPERTONIC_FLOW_MODES:
        return value
    return SUPERTONIC_FLOW_MODE_DEFAULT


def get_supertonic_flow_settings(mode = None):
    normalized = normalize_supertonic_flow_mode(mode)
    settings = dict(SUPERTONIC_FLOW_MODES[normalized])
    settings['mode'] = normalized
    return settings


def get_supertonic_flow_category(mode = None):
    settings = get_supertonic_flow_settings(mode)
    return 'repairli' if settings.get('repair_enabled') else 'repairsiz'


def list_supertonic_flow_modes():
    return [(key, dict(value)) for key, value in SUPERTONIC_FLOW_MODES.items()]
