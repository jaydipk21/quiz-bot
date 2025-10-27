
from .constants import BOT_WELCOME_MESSAGE, PYTHON_QUESTION_LIST
import string

LETTER_KEYS = list(string.ascii_uppercase)  # ["A","B","C","D",...]

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def _format_question(qobj: dict) -> str:
    """Render question text + options as A), B), C)..."""
    text = qobj.get("question_text", "").strip()
    opts = qobj.get("options") or []
    if opts:
        lines = [f"{LETTER_KEYS[i]}) {opt}" for i, opt in enumerate(opts)]
        text = text + "\n" + "\n".join(lines)
    return text

def _is_valid_choice(answer: str, qobj: dict) -> bool:
    """Allow either letter (A/B/...) or the full option text; open answers accepted."""
    if not answer or not str(answer).strip():
        return False
    opts = qobj.get("options") or []
    if not opts:                 # open answer question (not used here, but safe)
        return True
    ans = _normalize(str(answer))
    # letter?
    for i, letter in enumerate(LETTER_KEYS[:len(opts)]):
        if ans == letter.lower():
            return True
    # option text?
    return any(ans == _normalize(str(opt)) for opt in opts)

def _answer_matches_correct(user_answer: str, qobj: dict) -> bool:
    """Compare user's answer (letter or text) with the correct one (text in constants)."""
    opts = qobj.get("options") or []
    correct_text = _normalize(str(qobj.get("answer", "")))
    if not correct_text:
        return False

    ua = _normalize(str(user_answer))
    # If user sent a letter, resolve to text
    if len(ua) == 1 and ua in [c.lower() for c in LETTER_KEYS[:len(opts)]]:
        idx = [c.lower() for c in LETTER_KEYS].index(ua)
        if idx < len(opts):
            ua = _normalize(str(opts[idx]))

    return ua == correct_text


def generate_bot_responses(message, session):
    bot_responses = []

    current_question_id = session.get("current_question_id")
    if not current_question_id:
        bot_responses.append(BOT_WELCOME_MESSAGE)

    success, error = record_current_answer(message, current_question_id, session)

    if not success:
        return [error]

    next_question, next_question_id = get_next_question(current_question_id)

    if next_question:
        bot_responses.append(next_question)
    else:
        final_response = generate_final_response(session)
        bot_responses.append(final_response)

    session["current_question_id"] = next_question_id
    session.save()

    return bot_responses


def record_current_answer(answer, current_question_id, session):
    '''
    Validates and stores the answer for the current question to django session.
    Uses 1-based question IDs (so 1 == first question).
    '''
    # First interaction: nothing to record yet
    if current_question_id is None:
        return True, ""

    # Map 1-based id -> 0-based index
    q_index = current_question_id - 1
    if q_index < 0 or q_index >= len(PYTHON_QUESTION_LIST):
        return True, ""  # quiz already ended; nothing to record

    qobj = PYTHON_QUESTION_LIST[q_index]

    # Validate
    if not _is_valid_choice(answer, qobj):
        opts = qobj.get("options") or []
        if opts:
            letters = ", ".join(LETTER_KEYS[:len(opts)])
            return False, f"Please answer with one of: {letters} or the option text."
        return False, "Please provide a valid answer."

    # Store in session
    answers = session.get("answers") or {}
    answers[current_question_id] = str(answer).strip()
    session["answers"] = answers
    session.modified = True
    return True, ""

def get_next_question(current_question_id):
    '''
    Returns (next_question_text, next_question_id).
    current_question_id is 1-based; None means give the first question.
    '''
    if current_question_id is None:
        next_id = 1
    else:
        next_id = current_question_id + 1

    if 1 <= next_id <= len(PYTHON_QUESTION_LIST):
        qobj = PYTHON_QUESTION_LIST[next_id - 1]
        return _format_question(qobj), next_id

    # No more questions
    return None, None

def generate_final_response(session):
    '''
    Compute score using answers in session and PYTHON_QUESTION_LIST.
    Resets current_question_id so a new quiz can start fresh.
    '''
    answers = session.get("answers") or {}
    score = 0
    total = len(PYTHON_QUESTION_LIST)

    for i in range(1, total + 1):  # 1..N (1-based)
        qobj = PYTHON_QUESTION_LIST[i - 1]
        if i in answers and _answer_matches_correct(answers[i], qobj):
            score += 1

    # Reset for next run
    session["current_question_id"] = None
    session["answers"] = {}
    session.modified = True

    return f"Quiz complete! Your score is {score}/{total}. Thanks for playing!"
