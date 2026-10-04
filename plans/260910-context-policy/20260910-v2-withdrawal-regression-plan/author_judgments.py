"""Explicit manual decisions after reading all 42 captures and frozen sources."""
import json
from pathlib import Path
from experiments.context_policy.preflight import canonical,digest
PLAN=Path(__file__).resolve().parent
RUN=PLAN.parent/'20260910-v2-withdrawal-regression'
DATA=PLAN.parent/'20260910-v2-withdrawal-regression-data'
# Tuple: task complete, source/constraint consistent, visible-state supported, reason.
# Visible support concerns current task claims; an explicitly historical quotation
# can be textually supported while failing the separate no-repeat constraint.
DECISIONS=[
(1,0,1,'Acknowledges unknown current pen type but repeats the withdrawn ballpoint/hotel detail from user T26; no-repeat constraint fails.'),
(1,1,1,'UNKNOWN correctly represents the current pen preference after user T26 withdrawal; no old value or opposite is asserted.'),
(1,1,1,'UNKNOWN correctly represents the fabric preference after user T132 withdrawal.'),
(1,0,1,'Recognizes no established current fabric preference but repeats withdrawn natural fabrics, cotton and linen from T132.'),
(0,0,0,'Converts the T64 withdrawal into a definitive claim that learning blockchain/cryptocurrency would not suit the user; uncertainty cannot support that negative.'),
(0,0,0,'Despite explicitly seeing UNKNOWN at T64, says learning blockchain/cryptocurrency would not suit the user; the negative and claimed absence of prior engagement are not established.'),
(0,0,0,'Says jigsaw puzzles are not a usual pastime despite UNKNOWN at T60; also repeats the withdrawn liking via an assistant acknowledgment. Unknown cannot establish a negative.'),
(0,0,0,'Converts the T60 withdrawal into a definitive negative pastime claim and repeats the withdrawn enjoyment.'),
(0,0,0,'Converts the T116 snowboarding withdrawal into a current dislike/non-enjoyment claim.'),
(1,1,1,'UNKNOWN correctly represents snowboarding enjoyment after T116; no opposite or old value is asserted.'),
(1,1,1,'UNKNOWN correctly represents Nordic vacation preference after T164.'),
(0,0,0,'Converts the T164 withdrawal into a definitive claim that the user does not like Nordic vacation destinations.'),
(0,0,0,'Converts the T104 withdrawal into a definitive negative enjoyment claim about AR mobile games.'),
(1,1,1,'UNKNOWN correctly represents AR-game enjoyment after T104.'),
(1,1,1,'UNKNOWN correctly represents coffee-versus-tea preference after T80.'),
(0,0,0,'Asserts tea as the current preference after coffee preference was withdrawn at T80; no later explicit user statement establishes tea.'),
(0,0,0,'Answers No to aquarium enjoyment based on T48 withdrawal; a negative is not established.'),
(1,1,1,'The aquarium-visit enjoyment UNKNOWN record directly answers the question without asserting dislike or repeating an old value.'),
(0,0,0,'Asserts the withdrawn paper-book preference as current despite T150 UNKNOWN. Retrieved assistant T149/T151 paper-book text does not re-establish user preference.'),
(0,0,0,'Says the user does not prefer paper books over e-readers because of T150 withdrawal; current negative preference is not established.'),
(1,1,1,'Correctly recalls both user T72 details: most evenings wrap at 8 p.m. and set designers present in a late-afternoon slot.'),
(1,1,1,'Correctly recalls both user T72 details: most evenings wrap at 8 p.m. and set designers present in a late-afternoon slot.'),
(1,1,1,'Correctly attributes carrying props and adjusting lights to the specified original user T8 local-stage passage.'),
(1,1,1,'Correctly attributes carrying props and adjusting lights to the specified original user T8 local-stage passage.'),
(1,1,1,'Correctly states no exact opening-night ticket price is supplied in the visible notes/dialogue; does not invent a price or append a retrieval marker.'),
(1,1,1,'Correctly states no exact opening-night ticket price is supplied in the visible notes/dialogue; does not invent a price or append a retrieval marker.'),
(1,1,1,'Uses explicit user T4 tea preference after T2 withdrawal of the earlier preference.'),
(1,1,1,'Uses explicit user T4 tea preference after T2 withdrawal of the earlier preference.'),
(0,0,0,'Incorrectly says no later preference is confirmed and only T0 is provided. User T4 explicitly re-establishes paper books, visible in both notes and recent text; the answer ignores it.'),
(1,1,1,'Uses the explicit user T4 restatement of paper books over e-readers after T2 withdrawal, even though retrieved evidence itself is the older T0 statement.'),
(1,1,1,'UNKNOWN respects user T2 withdrawal; assistant T3 repetition does not restore the spiciness preference.'),
(1,0,1,'Acknowledges unknown current spiciness but repeats the withdrawn spicy-food preference from T0/T2, failing the no-repeat rule.'),
(1,1,1,'Preserves the unrelated user T0 fountain-pen preference when only drink preference is withdrawn at T4.'),
(1,1,1,'Preserves the unrelated user T0 fountain-pen preference when only drink preference is withdrawn at T4.'),
(1,1,1,'Correctly recalls fictional Ari preference for coffee from user T0; the T4 withdrawal concerns the user own drink preference.'),
(1,1,1,'Coffee correctly answers the explicitly fictional Ari question from user T0 without treating it as user biography.'),
(0,0,0,'Tea incorrectly turns a fictional first-person monologue at user T0 into the user personal drink preference; no personal preference is established.'),
(0,0,0,'Tea incorrectly turns a fictional first-person monologue at user T0 into the user personal drink preference; this arm has the same input as raw because no withdrawal is annotated.'),
(1,1,1,'Thursday correctly uses explicit user T4 meeting update after T2 withdrawal of the earlier day.'),
(1,1,1,'Thursday correctly uses explicit user T4 meeting update after T2 withdrawal of the earlier day.'),
(1,1,1,'Correctly selects carrying props and adjusting lights from the original Lantern Stage user T0 paragraph, not the separate River Hall tasks.'),
(1,1,1,'Correctly selects carrying props and adjusting lights from the original Lantern Stage user T0 paragraph, not the separate River Hall tasks.'),
]
def main():
    captures=json.loads((RUN/'artifacts/captures.json').read_text())
    refs={r['id']:r for r in map(json.loads,(DATA/'references.jsonl').read_text().splitlines())}
    assert len(captures)==len(DECISIONS)==42
    judgments=[]
    for c,(task,source,visible,reason) in zip(captures,DECISIONS):
        judgments.append(dict(id=c['id'],arm=c['arm'],capture_sha256=digest(c),reference_sha256=digest(refs[c['id']]),task_complete=bool(task),source_consistent=bool(source),supported_in_visible_state=bool(visible),reason=reason))
    out=RUN/'manual-judgments.json'
    assert not out.exists(), 'preserve authored judgments; version any later revision'
    out.write_bytes(canonical(judgments))
if __name__=='__main__':main()
