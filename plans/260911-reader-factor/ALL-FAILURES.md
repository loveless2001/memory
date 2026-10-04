# All answer failures and extraction deviations

Strict failures only; full passing and failing evidence is in review.json.

## direct / N09-1

Question: Is MAY-ree the pronunciation I supplied for my name?

Answer: Yes. You supplied MAH-ree.

Reference: No. You supplied MAH-ree.

Failed criteria: task_complete, source_consistent, supported_in_visible_state.

Exact previous messages, tokens and text reproduced; retain the prior source-reviewed judgment. The question asks whether MAY-ree was supplied by the user; the source instead supplies MAH-ree, while MAY-ree belongs to the assistant reply. The leading Yes is wrong and conflicts with the answer's correct MAH-ree value. A correct value in the explanation cannot rescue the wrong requested binary answer. The factual attribution within the explanatory clause remains correct.

Source:
- T0 user: My name is pronounced MAH-ree.
- T1 assistant: I will pronounce your name MAY-ree.
- T2 user: Please use the pronunciation I gave you, rather than your version.

## direct / N12-2

Question: What is my dessert preference?

Answer: You have not specified a preferred dessert.

Reference: You explicitly have no preferred dessert.

Failed criteria: task_complete.

Exact previous messages, tokens and text reproduced; retain the prior source-reviewed judgment. The source explicitly establishes no preferred dessert. Saying only that a preferred dessert has not been specified omits this known-none state and presents the absence of a positive named value. That narrow literal claim is source-supported, so support and consistency remain true; it does not fulfill the requested preference answer. This is still a failure of the targeted distinction, though the explanation differs from v1's categorical unknown claim.

Source:
- T0 user: I do not have a preferred dessert. This is an explicit personal fact, not a request to forget anything.
- T1 assistant: Understood.

## direct / H02-1

Question: Is Raven the surname spelling that I supplied for the reservation?

Answer: Yes. You supplied Ravn.

Reference: No. You supplied Ravn.

Failed criteria: task_complete, source_consistent, supported_in_visible_state.

Exact previous messages, tokens and text reproduced; retain the prior source-reviewed judgment. The queried spelling is Raven from the assistant; the user supplied Ravn. The answer gives Yes followed by the correct Ravn, producing the same contradictory binary response as v1. Correct open/other-form answers for this history do not repair this response.

Source:
- T0 user: Put the reservation under the surname Ravn. That is the spelling I am providing.
- T1 assistant: I have it under Raven.
- T2 user: Keep the exact spelling from my request.

## extracted_fact / H11-2

Question: Have I stated that velvet is not my preferred chair upholstery?

Answer: No. You have not stated a negative preference for velvet; you have explicitly stated no preference.

Reference: Yes. You do not prefer velvet for chair upholstery; no preferred alternative is established.

Failed criteria: task_complete, source_consistent, supported_in_visible_state.

The user explicitly stated velvet was not preferred. The answer incorrectly denies that statement and asserts explicit global no preference. It follows the erroneous none status; the shortened supplied quote omits the negative.

Source:
- T0 user: Velvet is not my preferred upholstery for a chair. I have not selected a preferred material.
- T1 assistant: Understood.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "chair upholstery", "quote": "I have not selected a preferred material.", "status": "none", "turn": 0, "value": null}
CURRENT QUESTION
Have I stated that velvet is not my preferred chair upholstery?
```

## extracted_fact / H11-3

Question: What have I told you about velvet chair upholstery?

Answer: You have not expressed a preference for velvet chair upholstery.

Reference: You do not prefer velvet for chair upholstery; no preferred alternative is established.

Failed criteria: task_complete.

The answer describes absence of a positive selected preference, but omits the supported explicit negative about velvet requested by this question. Its narrow statement is source-supported and faithful to the incomplete supplied record.

Source:
- T0 user: Velvet is not my preferred upholstery for a chair. I have not selected a preferred material.
- T1 assistant: Understood.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "chair upholstery", "quote": "I have not selected a preferred material.", "status": "none", "turn": 0, "value": null}
CURRENT QUESTION
What have I told you about velvet chair upholstery?
```

## extracted_fact / H11-4

Question: What is known about my chair-upholstery preference?

Answer: You have not selected a preferred material for your chair upholstery.

Reference: You do not prefer velvet for chair upholstery; no preferred alternative is established.

Failed criteria: task_complete.

The answer describes absence of a positive selected preference, but omits the supported explicit negative about velvet requested by this question. Its narrow statement is source-supported and faithful to the incomplete supplied record.

Source:
- T0 user: Velvet is not my preferred upholstery for a chair. I have not selected a preferred material.
- T1 assistant: Understood.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "chair upholstery", "quote": "I have not selected a preferred material.", "status": "none", "turn": 0, "value": null}
CURRENT QUESTION
What is known about my chair-upholstery preference?
```

## direct / X01-1

Question: Is Sorren the invoice-addressee spelling I supplied?

Answer: Yes. You supplied Soren.

Reference: No. You supplied Soren.

Failed criteria: task_complete, source_consistent, supported_in_visible_state.

The leading Yes wrongly affirms the queried distractor even though the following clause reports the correct supplied value. That clause cannot repair the binary answer.

Source:
- T0 user: The addressee on my invoice should be spelled Soren.
- T1 assistant: I have written Sorren.
- T2 user: Retain the spelling in my own sentence.

## direct / X04-1

Question: Was Pallas the label I supplied for my archive box?

Answer: Yes. You supplied Vesta.

Reference: No. You supplied Vesta.

Failed criteria: task_complete, source_consistent, supported_in_visible_state.

The leading Yes wrongly affirms the queried distractor even though the following clause reports the correct supplied value. That clause cannot repair the binary answer.

Source:
- T0 user: Use the label Vesta for my archive box.
- T1 assistant: I have noted your label.

## direct / X05-3

Question: What is my soup-temperature preference?

Answer: You have not specified a preferred serving temperature for soup.

Reference: You explicitly have no preferred soup temperature.

Failed criteria: task_complete.

The answer only says no positive preference has been specified/stated. This narrow claim is supported, but omits the explicitly established no-preference state requested by the question, using the same rule as N12-2.

Source:
- T0 user: I do not have a preferred serving temperature for soup. Please retain that as my explicit answer.
- T1 assistant: Understood.

## direct / X06-1

Question: Is snap-on my favourite pen-cap mechanism?

Answer: No. Your current preference for pen-cap mechanism is unknown.

Reference: No. You explicitly have no preferred pen cap mechanism.

Failed criteria: source_consistent, supported_in_visible_state.

The requested No is correct, but the explanation calls the preference unknown despite the explicit known-none fact. Required-answer correctness therefore passes while strict correctness fails.

Source:
- T0 user: I have no favourite pen-cap mechanism; that absence of preference is my position.
- T1 assistant: Understood.

## direct / X07-3

Question: What bath-towel pattern do I prefer?

Answer: You have not stated a preference for any bath-towel pattern.

Reference: You explicitly have no preferred bath towel pattern.

Failed criteria: task_complete.

The answer only says no positive preference has been specified/stated. This narrow claim is supported, but omits the explicitly established no-preference state requested by the question, using the same rule as N12-2.

Source:
- T0 user: No bath-towel pattern is a favourite of mine. I am stating no preference, rather than leaving the question unanswered.
- T1 assistant: Understood.

## oracle_query / X11-1

Question: Is a two-note bell my current favourite doorbell chime?

Answer: No. Your preference for doorbell chime is unknown.

Reference: Your current preference for doorbell chime is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: My favourite doorbell chime is a two-note bell.
- T1 assistant: Noted.
- T2 user: Remove my doorbell-chime preference from the personal details you retain.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "doorbell chime", "quote": "Remove my doorbell-chime preference from the personal details you retain.", "status": "unknown", "turn": 2, "value": null}
QUERY INTERPRETATION
{"candidate": "two-note bell", "operation": "matches_value"}
CURRENT QUESTION
Is a two-note bell my current favourite doorbell chime?
```

## oracle_fact / X11-2

Question: Is a single buzz my favourite doorbell chime now?

Answer: No. Your preference for a single buzz is unknown.

Reference: Your current preference for doorbell chime is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: My favourite doorbell chime is a two-note bell.
- T1 assistant: Noted.
- T2 user: Remove my doorbell-chime preference from the personal details you retain.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "doorbell chime", "quote": "Remove my doorbell-chime preference from the personal details you retain.", "status": "unknown", "turn": 2, "value": null}
CURRENT QUESTION
Is a single buzz my favourite doorbell chime now?
```

## extracted_fact / X11-2

Question: Is a single buzz my favourite doorbell chime now?

Answer: No. Your preference for a single buzz is unknown.

Reference: Your current preference for doorbell chime is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: My favourite doorbell chime is a two-note bell.
- T1 assistant: Noted.
- T2 user: Remove my doorbell-chime preference from the personal details you retain.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "doorbell chime", "quote": "Remove my doorbell-chime preference from the personal details you retain.", "status": "unknown", "turn": 2, "value": null}
CURRENT QUESTION
Is a single buzz my favourite doorbell chime now?
```

## oracle_query / X11-2

Question: Is a single buzz my favourite doorbell chime now?

Answer: No. Your preference for doorbell chime is unknown.

Reference: Your current preference for doorbell chime is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: My favourite doorbell chime is a two-note bell.
- T1 assistant: Noted.
- T2 user: Remove my doorbell-chime preference from the personal details you retain.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "doorbell chime", "quote": "Remove my doorbell-chime preference from the personal details you retain.", "status": "unknown", "turn": 2, "value": null}
QUERY INTERPRETATION
{"candidate": "single buzz", "operation": "matches_value"}
CURRENT QUESTION
Is a single buzz my favourite doorbell chime now?
```

## oracle_query / X12-1

Question: Do I currently prefer mountain silhouettes for desktop wallpaper?

Answer: No. You have not explicitly stated a preference for mountain silhouettes.

Reference: Your current preference for desktop wallpaper motif is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: For desktop wallpaper I prefer mountain silhouettes.
- T1 assistant: Noted.
- T2 user: Forget the personal note about my preferred desktop-wallpaper motif.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "desktop wallpaper motif", "quote": "Forget the personal note about my preferred desktop-wallpaper motif.", "status": "unknown", "turn": 2, "value": null}
QUERY INTERPRETATION
{"candidate": "mountain silhouettes", "operation": "matches_value"}
CURRENT QUESTION
Do I currently prefer mountain silhouettes for desktop wallpaper?
```

## oracle_fact / X12-2

Question: Are ocean waves my preferred desktop-wallpaper motif now?

Answer: No. Your preference for desktop-wallpaper motif is unknown.

Reference: Your current preference for desktop wallpaper motif is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: For desktop wallpaper I prefer mountain silhouettes.
- T1 assistant: Noted.
- T2 user: Forget the personal note about my preferred desktop-wallpaper motif.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "desktop wallpaper motif", "quote": "Forget the personal note about my preferred desktop-wallpaper motif.", "status": "unknown", "turn": 2, "value": null}
CURRENT QUESTION
Are ocean waves my preferred desktop-wallpaper motif now?
```

## extracted_fact / X12-2

Question: Are ocean waves my preferred desktop-wallpaper motif now?

Answer: No. Your preference for desktop-wallpaper motif is unknown.

Reference: Your current preference for desktop wallpaper motif is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: For desktop wallpaper I prefer mountain silhouettes.
- T1 assistant: Noted.
- T2 user: Forget the personal note about my preferred desktop-wallpaper motif.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "desktop wallpaper motif", "quote": "Forget the personal note about my preferred desktop-wallpaper motif.", "status": "unknown", "turn": 2, "value": null}
CURRENT QUESTION
Are ocean waves my preferred desktop-wallpaper motif now?
```

## oracle_query / X12-2

Question: Are ocean waves my preferred desktop-wallpaper motif now?

Answer: No. Your preference for desktop-wallpaper motif is unknown.

Reference: Your current preference for desktop wallpaper motif is unknown.

Failed criteria: task_complete, source_consistent, supported_in_visible_state, withdrawal_compliant.

The categorical leading No asserts a negative that the unknown current state cannot establish. A following uncertainty or lack-of-statement clause does not repair it under the frozen convention. This also violates the supplied unknown record; an epistemic-refusal reading is reported as sensitivity, not the primary score.

Source:
- T0 user: For desktop wallpaper I prefer mountain silhouettes.
- T1 assistant: Noted.
- T2 user: Forget the personal note about my preferred desktop-wallpaper motif.
- T3 assistant: Acknowledged.

Actual record/query message:
```
EVIDENCE RECORD
{"property": "desktop wallpaper motif", "quote": "Forget the personal note about my preferred desktop-wallpaper motif.", "status": "unknown", "turn": 2, "value": null}
QUERY INTERPRETATION
{"candidate": "ocean waves", "operation": "matches_value"}
CURRENT QUESTION
Are ocean waves my preferred desktop-wallpaper motif now?
```

## Extraction deviations

### R04

The source states a negative preference and no selected alternative. The generated none status conflates this with explicit global no preference. Its shortened quote omits the velvet negative, removing information that downstream selection needs.

Generated: `{"status":"none","value":null,"turn":0,"quote":"I have not selected a preferred material."}`

Gold: `{"status": "negative", "value": "Velvet", "turn": 0, "quote": "Velvet is not my preferred upholstery for a chair. I have not selected a preferred material."}`

### X03

Silver is a semantically sufficient contextual abbreviation of silver counter: the property and quote identify the counter. It does not match the frozen literal value string, so the deterministic comparison fails on the positive candidate and both lookup outputs. No alias normalization is added after results.

Generated: `{"status":"value","value":"silver","turn":0,"quote":"I am specifying the silver counter for my parcel pickup."}`

Gold: `{"status": "value", "value": "silver counter", "turn": 0, "quote": "I am specifying the silver counter for my parcel pickup."}`

### X09

The source states a negative preference and no selected alternative. The generated none status conflates this with explicit global no preference. The full negative statement remains in the quote, enabling downstream recovery despite the wrong typed state.

Generated: `{"status":"none","value":null,"turn":0,"quote":"I do not prefer laces for fastening my shoes. I have not chosen a preferred alternative."}`

Gold: `{"status": "negative", "value": "laces", "turn": 0, "quote": "I do not prefer laces for fastening my shoes. I have not chosen a preferred alternative."}`

### X10

The source states a negative preference and no selected alternative. The generated none status conflates this with explicit global no preference. The full negative statement remains in the quote, enabling downstream recovery despite the wrong typed state.

Generated: `{"status":"none","value":null,"turn":0,"quote":"Marble is not my preferred tabletop material. There is no specified preferred alternative."}`

Gold: `{"status": "negative", "value": "Marble", "turn": 0, "quote": "Marble is not my preferred tabletop material. There is no specified preferred alternative."}`

