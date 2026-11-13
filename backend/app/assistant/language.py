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
    if re.search(r'\b(?:what|why|how|when|which|compare|analy[sz]e|please|explain|find|keep|change|hours?|days?|mission)\b', lower):
        return 'en'
    return None


def request_language(request):
    return (text_language(request.text)
            or next((language for turn in reversed(request.conversation_history)
                     if (language := text_language(turn.text))), None)
            or 'vi')
