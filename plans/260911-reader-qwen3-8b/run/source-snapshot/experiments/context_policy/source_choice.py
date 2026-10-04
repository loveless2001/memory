"""Finite source-ID choices for note ranking, not free-form action evaluation.

The model can choose only currently available IDs, each once, then EOS. The
program controls syntax; no claim of learned format compliance follows. Quotes
still require source validation, exact budget admission and semantic review.
"""

from .note_budget import ranked_selector_messages


def choice_messages(tokenizer, previous, incoming, constraints, note_tokens=768):
    messages = ranked_selector_messages(tokenizer, previous, incoming, constraints, note_tokens)
    messages[0]['content'] = """Rank up to eight candidate USER QUOTATIONS by usefulness for unknown future questions.
Output only their candidate IDs, one per line, best first, then stop. No JSON or prose.
Favor concrete enduring context, decisions and corrections over generic questions.
User quotations can be drafts or third-party text; do not infer personal ownership.
The program retains withdrawals verbatim and admits whole quotes under the token cap.
Never reverse a withdrawal's meaning. You rank choices; the program enforces syntax
and budget. Select only from the supplied candidates, without repetition."""
    return messages


class SourceChoiceGrammar:
    def __init__(self, tokenizer, source_ids, max_choices=8):
        if not source_ids or len(source_ids) != len(set(source_ids)) or max_choices < 1:
            raise ValueError('nonempty distinct choices and a positive bound required')
        self.eos_id = tokenizer.eos_token_id
        if self.eos_id is None:
            raise ValueError('tokenizer must provide EOS')
        self.paths = {x: tuple(tokenizer.encode(x+'\n', add_special_tokens=False)) for x in source_ids}
        paths = list(self.paths.values())
        if any(not p or self.eos_id in p for p in paths):
            raise ValueError('invalid source-ID token path')
        if any(a == b[:len(a)] for i, a in enumerate(paths) for j, b in enumerate(paths) if i != j):
            raise ValueError('source-ID token paths must be distinct and prefix-free')
        self.max_choices = min(max_choices, len(paths))
        self.max_required_tokens = max(map(len, paths))*self.max_choices+1

    def _allowed(self, selected, partial):
        if not partial and len(selected) >= self.max_choices:
            return [self.eos_id]
        active = [p for key, p in self.paths.items() if key not in selected and p[:len(partial)] == partial]
        allowed = {p[len(partial)] for p in active if len(p) > len(partial)}
        if selected and not partial:
            allowed.add(self.eos_id)
        if not allowed:
            raise ValueError('incomplete source-ID path has no continuation')
        return sorted(allowed)

    def _scan(self, tokens):
        selected, partial, ended = [], (), False
        for token in tokens:
            if ended or token not in self._allowed(selected, partial):
                raise ValueError('token outside source-choice grammar')
            if token == self.eos_id:
                ended = True
                continue
            partial += (token,)
            complete = [key for key, path in self.paths.items() if key not in selected and path == partial]
            if complete:
                selected.append(complete[0]); partial = ()
        return selected, partial, ended

    def allowed_tokens(self, tokens):
        selected, partial, ended = self._scan(tokens)
        return [] if ended else self._allowed(selected, partial)

    def selected_ids(self, tokens):
        selected, partial, ended = self._scan(tokens)
        if partial or not ended or not selected:
            raise ValueError('source-choice generation did not complete at EOS')
        return selected
