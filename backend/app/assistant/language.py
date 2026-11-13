"""Choose the response language without changing mission interpretation."""
import re
import unicodedata


def text_language(text):
    lower = text.casefold()
    plain = ''.join(c for c in unicodedata.normalize('NFD', lower)
                    if unicodedata.category(c) != 'Mn').replace('đ', 'd')
    if re.search(r'\b(?:in english|bang tieng anh|tra loi tieng anh)\b', plain):
        return 'en'
    if re.search(r'\b(?:in vietnamese|bang tieng viet|tra loi tieng viet)\b', plain):
        return 'vi'
    if plain != lower:
        return 'vi'
    if re.search(r'\b(?:phan tich|so sanh|giu nguyen|nhiem vu|bao nhieu|khi nao|tim ngay)\b', plain):
        return 'vi'
    if re.search(r'\b(?:what|why|how|when|which|compare|analy[sz]e|explore|evaluate|assess|inspect|show|tell|please|explain|find|keep|change|hours?|days?|mission|january|february|march|april|may|june|july|august|september|october|november|december)\b', lower):
        return 'en'
    return None


def request_language(request, model_language=None):
    # Clarification answers are the latest user input; assistant questions never
    # determine the language. Numeric/date-only answers inherit the conversation.
    # Let semantic model detection handle new wording even after a different
    # conversation language. Pure timestamps/numbers must keep prior language.
    wording = re.sub(r'\b(?:utc|gmt)\b', '', ' '.join(
        [request.text, *(turn.answer for turn in request.clarifications)]), flags=re.I)
    semantic_language = model_language if re.search(r'[a-zA-Z]{3,}', wording) else None
    return (next((language for turn in reversed(request.clarifications)
                  if (language := text_language(turn.answer))), None)
            or text_language(request.text)
            or semantic_language
            or next((language for turn in reversed(request.conversation_history)
                     if (language := text_language(turn.text))), None)
            or model_language or 'vi')
