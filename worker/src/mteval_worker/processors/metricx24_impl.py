# coding=utf-8
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# modified version of https://github.com/google-research/metricx

"""Note that this includes modified version of the official implementation,
because of some bug fixes regarding batching.

See: https://github.com/google-research/metricx
     https://github.com/google-research/metricx/issues/2
"""

import copy
import dataclasses
import os
import tempfile
import warnings
from typing import Optional, Tuple, Union

import torch
import transformers
import transformers.modeling_outputs
from joblib import Memory
from torch import nn

import datasets

os.environ["WANDB_MODE"] = "disabled"  # disable wandb for inference
mem = Memory(verbose=0)

BaseModelOutput = transformers.modeling_outputs.BaseModelOutput
ModelOutput = transformers.modeling_outputs.ModelOutput

MT5Config = transformers.models.mt5.modeling_mt5.MT5Config
MT5PreTrainedModel = transformers.models.mt5.modeling_mt5.MT5PreTrainedModel
MT5Stack = transformers.models.mt5.modeling_mt5.MT5Stack

__HEAD_MASK_WARNING_MSG = (
    transformers.models.mt5.modeling_mt5.__HEAD_MASK_WARNING_MSG  # pylint: disable=protected-access
)


@dataclasses.dataclass
class MT5ForRegressionOutput(ModelOutput):
    loss: Optional[torch.FloatTensor] = None
    predictions: torch.FloatTensor = None


class MT5ForRegression(MT5PreTrainedModel):
    """MT5 model for regression."""

    def __init__(self, config: MT5Config):
        super().__init__(config)
        self.model_dim = config.d_model

        self.shared = nn.Embedding(config.vocab_size, config.d_model)

        encoder_config = copy.deepcopy(config)
        encoder_config.is_decoder = False
        encoder_config.use_cache = False
        encoder_config.is_encoder_decoder = False
        self.encoder = MT5Stack(encoder_config, self.shared)

        decoder_config = copy.deepcopy(config)
        decoder_config.is_decoder = True
        decoder_config.is_encoder_decoder = False
        decoder_config.num_layers = config.num_decoder_layers
        self.decoder = MT5Stack(decoder_config, self.shared)

        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Initialize weights and apply final processing
        self.post_init()

        # Model parallel
        self.model_parallel = False
        self.device_map = None

    def forward(
        self,
        input_ids: Optional[torch.LongTensor] = None,
        attention_mask: Optional[torch.FloatTensor] = None,
        decoder_attention_mask: Optional[torch.BoolTensor] = None,
        head_mask: Optional[torch.FloatTensor] = None,
        decoder_head_mask: Optional[torch.FloatTensor] = None,
        cross_attn_head_mask: Optional[torch.Tensor] = None,
        encoder_outputs: Optional[Tuple[Tuple[torch.Tensor]]] = None,
        past_key_values: Optional[Tuple[Tuple[torch.Tensor]]] = None,
        inputs_embeds: Optional[torch.FloatTensor] = None,
        decoder_inputs_embeds: Optional[torch.FloatTensor] = None,
        labels: Optional[torch.FloatTensor] = None,
        use_cache: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None,
    ) -> Union[Tuple[torch.FloatTensor], MT5ForRegressionOutput]:
        use_cache = use_cache if use_cache is not None else self.config.use_cache
        return_dict = (
            return_dict if return_dict is not None else self.config.use_return_dict
        )

        # FutureWarning: head_mask was separated into two input args - head_mask,
        # decoder_head_mask
        if head_mask is not None and decoder_head_mask is None:
            if self.config.num_layers == self.config.num_decoder_layers:
                warnings.warn(__HEAD_MASK_WARNING_MSG, FutureWarning)
                decoder_head_mask = head_mask

        # Encode if needed (training, first prediction pass)
        if encoder_outputs is None:
            # Convert encoder inputs in embeddings if needed
            encoder_outputs = self.encoder(
                input_ids=input_ids,
                attention_mask=attention_mask,
                inputs_embeds=inputs_embeds,
                head_mask=head_mask,
                output_attentions=output_attentions,
                output_hidden_states=output_hidden_states,
                return_dict=return_dict,
            )
        elif return_dict and not isinstance(encoder_outputs, BaseModelOutput):
            encoder_outputs = BaseModelOutput(
                last_hidden_state=encoder_outputs[0],
                hidden_states=encoder_outputs[1] if len(encoder_outputs) > 1 else None,
                attentions=encoder_outputs[2] if len(encoder_outputs) > 2 else None,
            )

        hidden_states = encoder_outputs[0]

        if self.model_parallel:
            torch.cuda.set_device(self.decoder.first_device)

        # Create 1 step of dummy input for the decoder.
        batch_size = input_ids.size(0)
        decoder_input_ids = torch.LongTensor([0]).repeat(batch_size).reshape(-1, 1)
        if torch.cuda.is_available():
            decoder_input_ids = decoder_input_ids.to(torch.device("cuda"))

        # Set device for model parallelism
        if self.model_parallel:
            torch.cuda.set_device(self.decoder.first_device)
            hidden_states = hidden_states.to(self.decoder.first_device)
            if decoder_input_ids is not None:
                decoder_input_ids = decoder_input_ids.to(self.decoder.first_device)
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.decoder.first_device)
            if decoder_attention_mask is not None:
                decoder_attention_mask = decoder_attention_mask.to(
                    self.decoder.first_device
                )

        # Decode
        decoder_outputs = self.decoder(
            input_ids=decoder_input_ids,
            attention_mask=decoder_attention_mask,
            inputs_embeds=decoder_inputs_embeds,
            past_key_values=past_key_values,
            encoder_hidden_states=hidden_states,
            encoder_attention_mask=attention_mask,
            head_mask=decoder_head_mask,
            cross_attn_head_mask=cross_attn_head_mask,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        sequence_output = decoder_outputs[0]

        # Set device for model parallelism
        if self.model_parallel:
            torch.cuda.set_device(self.encoder.first_device)
            self.lm_head = self.lm_head.to(self.encoder.first_device)
            sequence_output = sequence_output.to(self.lm_head.weight.device)

        if self.config.tie_word_embeddings:
            # Rescale output before projecting on vocab
            # See
            # https://github.com/tensorflow/mesh/blob/fa19d69eafc9a482aff0b59ddd96b025c0cb207d/mesh_tensorflow/transformer/transformer.py#L586
            sequence_output = sequence_output * (self.model_dim**-0.5)

        lm_logits = self.lm_head(sequence_output)

        # 250089 = <extra_id_10>
        predictions = lm_logits[:, 0, 250089]

        # Clip to 0 to 25
        predictions = torch.clamp(predictions, 0, 25)

        loss = None
        if labels is not None:
            loss_fct = nn.MSELoss()
            # move labels to correct device to enable PP
            labels = labels.to(predictions.device)
            loss = loss_fct(predictions.view(-1), labels.view(-1))

        return MT5ForRegressionOutput(
            loss=loss,
            predictions=predictions,
        )


class Model:
    def __init__(
        self,
        model_name_or_path,
        tokenizer,
        batch_size,
        max_input_length,
    ):
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            self.per_device_batch_size = batch_size // torch.cuda.device_count()
        else:
            self.device = torch.device("cpu")
            self.per_device_batch_size = batch_size

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(tokenizer)

        self.model = MT5ForRegression.from_pretrained(
            model_name_or_path, torch_dtype="auto"
        )

        self.max_input_length = max_input_length

        self.model.to(self.device)
        self.model.eval()

    def predict(
        self,
        sources,
        hypotheses,
    ):
        ds, data_collator = get_dataset_and_data_collator(
            sources,
            hypotheses,
            self.tokenizer,
            self.max_input_length,
            self.device,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            training_args = transformers.TrainingArguments(
                output_dir=tmpdir,
                per_device_eval_batch_size=self.per_device_batch_size,
                dataloader_pin_memory=False,
            )
            trainer = transformers.Trainer(
                model=self.model,
                args=training_args,
                data_collator=data_collator,
            )
            predictions, _, _ = trainer.predict(test_dataset=ds["test"])

        scores = [float(p) for p in predictions]
        return scores


def get_dataset_and_data_collator(
    sources: list[str], hypotheses: list[str], tokenizer, max_input_length: int, device
):
    """Gets the test dataset for prediction.

    If `is_qe` is true, the input data must have "hypothesis" and "source" fields.
    If it is false, there must be "hypothesis" and "reference" fields.

    Padded to the longest sequence in the batch, see: https://github.com/google-research/metricx/issues/2

    Args:
      input_file: The path to the jsonl input file.
      tokenizer: The tokenizer to use.
      max_input_length: The maximum input sequence length.
      device: The ID of the device to put the PyTorch tensors on.
      is_qe: Indicates whether the metric is a QE metric or not.

    Returns:
      The dataset.
    """
    examples = [
        {
            "src": src.strip(),
            "tgt": tgt.strip(),
        }
        for src, tgt in zip(sources, hypotheses)
    ]
    ds = datasets.Dataset.from_list(examples)
    ds = datasets.DatasetDict({"test": ds})

    def _make_input(example):
        example["input"] = "source: " + example["src"] + " candidate: " + example["tgt"]
        return example

    def _tokenize(example):
        return tokenizer(
            example["input"],
            max_length=max_input_length,
            truncation=True,
            padding=False,
        )

    def _remove_eos(example):
        example["input_ids"] = example["input_ids"][:-1]
        example["attention_mask"] = example["attention_mask"][:-1]
        return example

    ds = ds.map(_make_input)
    ds = ds.map(_tokenize)
    ds = ds.map(_remove_eos)
    ds.set_format(
        type="torch",
        columns=["input_ids", "attention_mask"],
        device=device,
        output_all_columns=True,
    )
    data_collator = transformers.DataCollatorWithPadding(
        tokenizer=tokenizer,
        padding=True,
    )
    return ds, data_collator
