"""Answer-only supervision with the exact inference prefix and selected logits."""
import torch
import torch.nn.functional as F
from .broader_protocol import answer_prefix_ids


def encode_answer(tokenizer,messages,answer,max_tokens=8192,max_answer_tokens=192):
    if not isinstance(answer,str) or not answer.strip():raise ValueError('nonempty reviewed answer required')
    prefix=answer_prefix_ids(tokenizer,messages)
    targets=tokenizer.encode(answer,add_special_tokens=False)+[tokenizer.eos_token_id]
    if tokenizer.eos_token_id in targets[:-1]:raise ValueError('embedded EOS in target')
    if len(prefix)+len(targets)>max_tokens:raise ValueError('training sequence exceeds cap; no truncation')
    if len(targets)>max_answer_tokens:raise ValueError('answer exceeds generation cap')
    return {'input_ids':prefix+targets,'prefix_tokens':len(prefix),'target_ids':targets,
            'prediction_positions':list(range(len(prefix)-1,len(prefix)+len(targets)-1)),
            'supervised_tokens':len(targets),'source_tokens_masked':len(prefix),'action_tokens_supervised':0}


def answer_loss(logits,target_ids):
    if logits.ndim!=2 or target_ids.ndim!=1 or logits.shape[0]!=len(target_ids):
        raise ValueError('one selected next-token logit per answer target required')
    return F.cross_entropy(logits.float(),target_ids,reduction='mean')


def cast_training_parameters(model):
    # Keep rotary and other buffers in their original precision. A blanket
    # model.bfloat16() would round floating buffers and alter later FP32 inference.
    for parameter in model.parameters():
        parameter.data=parameter.data.to(torch.float32 if parameter.requires_grad else torch.bfloat16)


def learning_rate(step,total_steps,peak=1e-4,warmup_steps=3):
    """Fixed warmup then linear decay; step is one-based."""
    if not 1<=step<=total_steps:raise ValueError('optimizer step outside frozen schedule')
    if step<=warmup_steps:return peak*step/warmup_steps
    return peak*(total_steps-step)/(total_steps-warmup_steps)
