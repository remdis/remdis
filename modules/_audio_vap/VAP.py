import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from typing import Optional

from vap.objective import VAPObjective
from vap.utils.utils import (
    everything_deterministic,
    vad_fill_silences,
    vad_omit_spikes,
)
everything_deterministic()

class VAP(nn.Module):
    def __init__(
        self,
        encoder: nn.Module,
        transformer: nn.Module,
        bin_times: list[float] = [0.2, 0.4, 0.6, 0.8],
        frame_hz: int = 50,
    ):
        super().__init__()
        self.encoder = encoder
        self.transformer = transformer
        self.objective = VAPObjective(bin_times=bin_times, frame_hz=frame_hz)
        self.frame_hz = frame_hz
        self.dim: int = getattr(self.transformer, "dim", 256)

        # Outputs
        # Voice activity objective -> x1, x2 -> logits ->  BCE
        self.va_classifier = nn.Linear(self.dim, 1)
        self.vap_head = nn.Linear(self.dim, self.objective.n_classes)

    @property
    def horizon_time(self) -> float:
        return self.objective.horizon_time

    @property
    def sample_rate(self) -> int:
        return self.encoder.sample_rate

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def extract_labels(self, vad: Tensor) -> Tensor:
        return self.objective.get_labels(vad)

    def vad_loss(self, vad_output, vad):
        return F.binary_cross_entropy_with_logits(vad_output, vad)

    def encode_audio(self, audio: torch.Tensor) -> tuple[Tensor, Tensor]:
        assert (
            audio.shape[1] == 2
        ), f"audio VAP ENCODER: {audio.shape} != (B, 2, n_samples)"
        x1 = self.encoder(audio[:, :1])  # speaker 1
        x2 = self.encoder(audio[:, 1:])  # speaker 2
        return x1, x2

    def head(self, x: Tensor, x1: Tensor, x2: Tensor) -> tuple[Tensor, Tensor]:
        v1 = self.va_classifier(x1)
        v2 = self.va_classifier(x2)
        vad = torch.cat((v1, v2), dim=-1)
        logits = self.vap_head(x)
        return logits, vad
    
    def forward(self, waveform: Tensor, attention: bool = False) -> dict[str, Tensor]:
        x1, x2 = self.encode_audio(waveform)
        out = self.transformer(x1, x2, attention=attention)
        logits, vad = self.head(out["x"], out["x1"], out["x2"])
        out["logits"] = logits
        out["vad"] = vad
        max_values_per_row, idx = torch.max(out["logits"], dim=2)
        return out

    def entropy(self, probs: Tensor) -> Tensor:
        """
        Calculate entropy over each projection-window prediction (i.e. over
        frames/time) If we have C=256 possible states the maximum bit entropy
        is 8 (2^8 = 256) this means that the model have a one in 256 chance
        to randomly be right. The model can't do better than to uniformly
        guess each state, it has learned (less than) nothing. We want the
        model to have low entropy over the course of a dialog, "thinks it
        understands how the dialog is going", it's a measure of how close the
        information in the unseen data is to the knowledge encoded in the
        training data.
        """
        h = -probs * probs.log2()  # Entropy
        return h.sum(dim=-1).cpu()  # average entropy per frame

    def aggregate_probs(
        self,
        probs: Tensor,
        now_lims: list[int] = [0, 1],
        future_lims: list[int] = [2, 3],
    ) -> dict[str, Tensor]:
        # first two bins
        p_now = self.objective.probs_next_speaker_aggregate(
            probs, from_bin=now_lims[0], to_bin=now_lims[-1]
        ).cpu()
        p_future = self.objective.probs_next_speaker_aggregate(
            probs, from_bin=future_lims[0], to_bin=future_lims[1]
        ).cpu()
        # P over all
        max_idx = self.objective.n_bins - 1
        pa = self.objective.probs_next_speaker_aggregate(probs, 0, max_idx).cpu()
        p = []
        for i in range(0, max_idx + 1):
            p.append(self.objective.probs_next_speaker_aggregate(probs, i, i).cpu())
        p = torch.stack(p)
        return {
            "p_now": p_now,
            "p_future": p_future,
            "p_all": pa,
            "p": p,
        }

    @torch.inference_mode()
    def probs(
        self,
        waveform: Tensor,
        vad: Optional[Tensor] = None,
        now_lims: list[int] = [0, 1],
        future_lims: list[int] = [2, 3],
    ) -> dict[str, Tensor]:
        """"""
        out = self(waveform)
        probs = out["logits"].softmax(dim=-1)
        vap_vad = out["vad"].sigmoid()
        h = self.entropy(probs)
        ret = {
            "probs": probs,
            "vad": vap_vad,
            "H": h,
        }

        # Next speaker aggregate probs
        probs_agg = self.aggregate_probs(probs, now_lims, future_lims)
        ret.update(probs_agg)

        # If ground truth voice activity is known we can calculate the loss
        if vad is not None:
            labels = self.objective.get_labels(vad)
            ret["loss"] = self.objective.loss_vap(
                out["logits"], labels, reduction="none"
            ).cpu()
        return ret

    @torch.inference_mode()
    def vad(
        self,
        waveform: Tensor,
        max_fill_silence_time: float = 0.02,
        max_omit_spike_time: float = 0.02,
        vad_cutoff: float = 0.5,
    ) -> Tensor:
        """
        Extract (binary) Voice Activity Detection from model
        """
        vad = (self(waveform)["vad"].sigmoid() >= vad_cutoff).float()
        for b in range(vad.shape[0]):
            # TODO: which order is better?
            vad[b] = vad_fill_silences(
                vad[b], max_fill_time=max_fill_silence_time, frame_hz=self.frame_hz
            )
            vad[b] = vad_omit_spikes(
                vad[b], max_omit_time=max_omit_spike_time, frame_hz=self.frame_hz
            )
        return vad


def build_model():
    encoder = EncoderCPC()
    transformer = TransformerStereo()
    model = VAP(encoder, transformer)
    return model


if __name__ == "__main__":

    from vap.modules.encoder import EncoderCPC
    from torchsummary import summary
    # from vap.modules.encoder_hubert import EncoderHubert
    from vap.modules.modules import TransformerStereo

    encoder = EncoderCPC()
    # encoder = EncoderHubert()
    transformer = TransformerStereo()

    model = VAP(encoder, transformer)
    if torch.cuda.is_available(): model.cuda()
    summary(model, (2, 32000))


    x = torch.randn(1, 2, 32000)
    out = model(x)
