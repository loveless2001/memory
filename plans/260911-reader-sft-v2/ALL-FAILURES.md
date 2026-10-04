# Every strict failure

Full source histories and actual prompts are attached to each judgment in review.json.

## prior / N01-1

Question: Would it be accurate to say swimming is my preferred exercise now?

Reference: My current exercise preference is unknown.

Answer: No. Your current exercise preference is unknown.

Required answer correct: False. Exact prior adapter messages, token sequence and text verified; retain the prior source-checked author judgment. Under the frozen primary convention, the leading No is a definite negative where withdrawal establishes unknown; the following unknown statement does not repair it. The question asks whether an assertion would be accurate and also admits an epistemic refusal-to-assert interpretation. Retain the frozen judgment and show the predeclared separate N01 sensitivity. No old positive assignment is restated.

## prior / N09-1

Question: Is MAY-ree the pronunciation I supplied for my name?

Reference: No. You supplied MAH-ree.

Answer: Yes. You supplied the pronunciation MAH-ree.

Required answer correct: False. Exact prior adapter messages, token sequence and text verified; retain the prior source-checked author judgment. The queried option is MAY-ree, which the assistant supplied, whereas the user supplied MAH-ree. The answer says Yes and then correctly states MAH-ree, making its binary answer wrong and internally inconsistent. The correct explanatory value does not repair the wrong requested yes/no response. The explicit MAH-ree attribution is correct; this judgment does not infer an internal ownership mechanism from the polarity error.

## prior / N12-2

Question: What is my dessert preference?

Reference: You explicitly have no preferred dessert.

Answer: Your current dessert preference is unknown.

Required answer correct: False. Exact prior adapter messages, token sequence and text verified; retain the prior source-checked author judgment. The user explicitly stated that they have no preferred dessert, without any withdrawal. This is a known no-preference position. The answer incorrectly reports unknown, losing a required answer that the base model answered correctly.

## prior / H02-1

Question: Is Raven the surname spelling that I supplied for the reservation?

Reference: No. You supplied Ravn.

Answer: Yes. You supplied the spelling Ravn.

Required answer correct: False. The candidate in the question is Raven, the assistant spelling. The user supplied Ravn. The leading Yes is wrong even though the following clause correctly supplies Ravn, so the answer is internally inconsistent. The correct explanatory spelling cannot rescue its requested binary polarity; this repeats the type of contradiction seen in N09-1.

## prior / H05-3

Question: What is my envelope-size preference?

Reference: You have explicitly stated that you have no preferred envelope size.

Answer: You have not stated a preference for envelope size.

Required answer correct: False. The user explicitly states that they do not have a favourite envelope size and asks that this position be retained. The answer instead says that no preference has been stated, treating the known no-preference position as missing information. It does not provide the required known-none answer. A lack of a positive named value does not erase the explicit position.

## prior / H06-4

Question: What is known about my favourite curtain fabric?

Reference: You have explicitly stated that you have no preferred curtain fabric.

Answer: Your current preference for curtain fabric is unknown.

Required answer correct: False. The full source explicitly establishes no favourite, with no withdrawal. The answer incorrectly reports unknown. Known no-preference is distinct from missing information; the binary candidate question requires No under the frozen reference convention.

## prior / H07-1

Question: Is oval my favourite breakfast-bowl shape?

Reference: No. You have explicitly stated that you have no preferred breakfast bowl shape.

Answer: Your current preference for breakfast-bowl shape is unknown.

Required answer correct: False. The full source explicitly establishes no favourite, with no withdrawal. The answer incorrectly reports unknown. Known no-preference is distinct from missing information; the binary candidate question requires No under the frozen reference convention.

## prior / H11-4

Question: What is known about my chair-upholstery preference?

Reference: You do not prefer velvet for chair upholstery; no preferred alternative is established.

Answer: Your current preferred upholstery for a chair is unknown. You have not selected a preferred material.

Required answer correct: False. The source establishes a known negative preference: velvet is not preferred, while an alternative remains unspecified. The answer only reports the unspecified positive alternative and omits the known negative requested by the broad what-is-known question. Its stated claims are source-supported, so this is an incomplete required answer rather than an invented alternative or source contradiction.

## adapted / N01-1

Question: Would it be accurate to say swimming is my preferred exercise now?

Reference: My current exercise preference is unknown.

Answer: No. Your current preference for exercise is unknown.

Required answer correct: False. The leading No remains wrong under the frozen UNKNOWN-versus-negative convention, even with a following unknown clause. The current exercise preference was withdrawn. The same question also permits an epistemic refusal-to-assert reading; report that generous sensitivity separately without changing the primary judgment.

## adapted / N09-1

Question: Is MAY-ree the pronunciation I supplied for my name?

Reference: No. You supplied MAH-ree.

Answer: Yes. You supplied MAH-ree.

Required answer correct: False. The question asks whether MAY-ree was supplied by the user; the source instead supplies MAH-ree, while MAY-ree belongs to the assistant reply. The leading Yes is wrong and conflicts with the answer's correct MAH-ree value. A correct value in the explanation cannot rescue the wrong requested binary answer. The factual attribution within the explanatory clause remains correct.

## adapted / N12-2

Question: What is my dessert preference?

Reference: You explicitly have no preferred dessert.

Answer: You have not specified a preferred dessert.

Required answer correct: False. The source explicitly establishes no preferred dessert. Saying only that a preferred dessert has not been specified omits this known-none state and presents the absence of a positive named value. That narrow literal claim is source-supported, so support and consistency remain true; it does not fulfill the requested preference answer. This is still a failure of the targeted distinction, though the explanation differs from v1's categorical unknown claim.

## adapted / H02-1

Question: Is Raven the surname spelling that I supplied for the reservation?

Reference: No. You supplied Ravn.

Answer: Yes. You supplied Ravn.

Required answer correct: False. The queried spelling is Raven from the assistant; the user supplied Ravn. The answer gives Yes followed by the correct Ravn, producing the same contradictory binary response as v1. Correct open/other-form answers for this history do not repair this response.

## adapted / H09-4

Question: What notebook-binding preference is established?

Reference: You do not prefer spiral binding for notebook binding; no preferred alternative is established.

Answer: You explicitly reject spiral binding. Your preferred binding is unknown.

Required answer correct: True. The source says spiral binding is not preferred and no alternative has been selected. The answer supplies a correct negative and unknown alternative but strengthens non-preference into an explicit rejection. An unqualified rejection is not established by the source; the required answer remains correct while whole-answer support fails. A generous reading of reject as merely reject-as-the-preferred-option is reported separately as a sensitivity.
