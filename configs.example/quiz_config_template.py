"""
Template for quiz configuration - copy to configs/quizX_config.py and customize.

This file shows the structure but does not contain real question tags.
"""

QUIZ_CONFIG = {
    'quiz_id': 5,  # Quiz number (1-6)
    'quiz_name': 'Network Flow',  # Descriptive name
    'rubric_folder': 'quiz5',  # Folder in rubrics/ (unzip course materials here)
    
    'question_groups': [
        {
            'id': 'q1',  # Unique identifier for this question group
            'name': 'Network Flow',  # Descriptive name for output folder
            # Variant tags: each tag identifies ONE question variant
            # e.g., [1.9] in CSV means student got variant 9 of question 1
            'variant_tags': ['1.1', '1.2', '1.3', '1.4', '1.5', '1.6'],  # CUSTOMIZE
            'num_parts': 2,  # Number of subparts (a, b, c, etc.) - same for all variants
            'latex_line_range': (45, 671),  # Line range in rubric file
            'num_versions': 6,  # Number of question variants
            'points': 3,  # Total points for this question
            # Optional: Manual image mapping for TikZ graphs
            # Only needed if rubric uses TikZ instead of \includegraphics
            # 'image_map': {
            #     1: 'graph1.png',
            #     2: 'graph2.jpg',
            #     # ... map each version to its image file
            # }
            'page_break': 'same-page',
            #each-part for page break before each part
            #each-part-not-first for page break before each part except part a
            # Optional: expected number of pages per student PDF.
            # Any PDF exceeding this count is auto-moved to a separate
            # *_overflow_merged.pdf instead of the main merged PDF.
            'expected_pages': 2,
        },
        {
            'id': 'q2',
            'name': 'Bipartite Matching',
            'variant_tags': ['2.1', '2.2', '2.3', '2.4', '2.5'],  # CUSTOMIZE
            'num_parts': 3,  # Number of subparts
            'latex_line_range': (703, 1202),
            'num_versions': 5,
            'points': 6,
            'page_break': 'same-page',
            # 'expected_pages': 4,
        }
    ]
}

