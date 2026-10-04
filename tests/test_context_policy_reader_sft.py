import unittest
import torch
from experiments.context_policy.reader_sft_protocol import encode_answer,answer_loss,learning_rate,cast_training_parameters


class TinyTokenizer:
    eos_token_id=99
    def apply_chat_template(self,messages,tokenize=True,add_generation_prompt=True):return [1,2,3,4]
    def encode(self,text,add_special_tokens=False):
        return [5,6] if text=='ANSWER\n' else [7,8]


class AnswerSupervisionTest(unittest.TestCase):
    def test_only_next_answer_and_eos_positions_are_supervised(self):
        x=encode_answer(TinyTokenizer(),[{'role':'user','content':'source'}],'unknown')
        self.assertEqual(x['input_ids'],[1,2,3,4,5,6,7,8,99])
        self.assertEqual(x['prediction_positions'],[5,6,7])
        self.assertEqual(x['target_ids'],[7,8,99])
        self.assertEqual(x['action_tokens_supervised'],0)
        self.assertEqual(x['source_tokens_masked'],6)

    def test_selected_loss_has_no_prompt_target_loss(self):
        torch.manual_seed(7)
        full=torch.randn(9,100,requires_grad=True)
        x=encode_answer(TinyTokenizer(),[],'unknown')
        loss=answer_loss(full[x['prediction_positions']],torch.tensor(x['target_ids']))
        expected=torch.nn.functional.cross_entropy(full[5:8],torch.tensor([7,8,99]))
        torch.testing.assert_close(loss,expected)
        loss.backward()
        self.assertEqual(float(full.grad[:5].abs().sum()),0)
        self.assertEqual(float(full.grad[8:].abs().sum()),0)
        self.assertGreater(float(full.grad[5:8].abs().sum()),0)

    def test_no_silent_target_truncation_or_empty_supervision(self):
        with self.assertRaises(ValueError):encode_answer(TinyTokenizer(),[],'')
        with self.assertRaises(ValueError):encode_answer(TinyTokenizer(),[],'unknown',max_tokens=8)
        with self.assertRaises(ValueError):encode_answer(TinyTokenizer(),[],'unknown',max_answer_tokens=2)
        with self.assertRaises(ValueError):answer_loss(torch.zeros(2,10),torch.ones(3,dtype=torch.long))

    def test_fixed_schedule_bounds(self):
        self.assertAlmostEqual(learning_rate(1,48),1e-4/3)
        self.assertEqual(learning_rate(3,48),1e-4)
        self.assertEqual(learning_rate(48,48),0)
        with self.assertRaises(ValueError):learning_rate(49,48)

    def test_training_precision_preserves_frozen_buffers_and_adapter_precision(self):
        model=torch.nn.Module()
        model.register_parameter('base',torch.nn.Parameter(torch.tensor([1.25]),requires_grad=False))
        model.register_parameter('adapter',torch.nn.Parameter(torch.tensor([0.01])))
        model.register_buffer('rotary',torch.tensor([0.123456789],dtype=torch.float32))
        before=model.rotary.clone()
        cast_training_parameters(model)
        self.assertEqual(model.base.dtype,torch.bfloat16)
        self.assertEqual(model.adapter.dtype,torch.float32)
        self.assertEqual(model.rotary.dtype,torch.float32)
        torch.testing.assert_close(model.rotary,before,rtol=0,atol=0)


if __name__=='__main__':unittest.main()
