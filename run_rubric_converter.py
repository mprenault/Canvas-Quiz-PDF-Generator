from core.rubric_converter import convert_rubric_to_templates, save_templates
from configs.quiz2_config import QUIZ_CONFIG

templates = convert_rubric_to_templates(QUIZ_CONFIG)
save_templates(templates, QUIZ_CONFIG['quiz_id'])
