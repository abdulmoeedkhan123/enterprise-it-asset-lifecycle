from __future__ import annotations

from django import forms

from .models import Asset, LifecycleStatus, SanitisationResult
from .services import ALLOWED_TRANSITIONS


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = (
            "asset_id",
            "asset_type",
            "manufacturer",
            "model",
            "serial_ref",
            "site",
            "department",
            "custodian_ref",
            "purchase_date",
            "warranty_end",
            "return_due_date",
            "sanitisation_required",
            "sanitisation_result",
            "sanitisation_evidence_ref",
            "disposal_evidence_ref",
            "source_last_updated",
        )
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_end": forms.DateInput(attrs={"type": "date"}),
            "return_due_date": forms.DateInput(attrs={"type": "date"}),
            "source_last_updated": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if (
            self.instance.pk
            and self.instance.lifecycle_status
            in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
            and self.instance.sanitisation_required
            and cleaned_data.get("sanitisation_required") is False
        ):
            self.add_error(
                "sanitisation_required",
                "Sanitisation requirements cannot be removed after disposition review starts.",
            )
        return cleaned_data


class TransitionForm(forms.Form):
    to_status = forms.ChoiceField(label="New lifecycle status")
    reason = forms.CharField(max_length=255)
    return_due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    sanitisation_result = forms.ChoiceField(
        required=False,
        choices=(("", "---------"), *SanitisationResult.choices),
    )
    sanitisation_evidence_ref = forms.CharField(max_length=64, required=False)
    disposal_evidence_ref = forms.CharField(max_length=64, required=False)

    def __init__(self, *args, asset: Asset, **kwargs):
        super().__init__(*args, **kwargs)
        choices = sorted(
            ALLOWED_TRANSITIONS.get(asset.lifecycle_status, set()),
            key=str,
        )
        self.fields["to_status"].choices = [(value, value) for value in choices]
        self.asset = asset

    def clean(self):
        cleaned_data = super().clean()
        to_status = cleaned_data.get("to_status")
        if to_status == LifecycleStatus.RETURN_PENDING and not cleaned_data.get(
            "return_due_date"
        ):
            self.add_error(
                "return_due_date", "A due date is required for a return-pending asset."
            )
        if (
            to_status
            in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
            and self.asset.sanitisation_required
        ):
            result = cleaned_data.get("sanitisation_result") or self.asset.sanitisation_result
            sanitisation_ref = (
                cleaned_data.get("sanitisation_evidence_ref")
                or self.asset.sanitisation_evidence_ref
            )
            disposal_ref = (
                cleaned_data.get("disposal_evidence_ref")
                or self.asset.disposal_evidence_ref
            )
            if result != SanitisationResult.PASSED:
                self.add_error(
                    "sanitisation_result",
                    "Passed sanitisation is required before disposal.",
                )
            if not sanitisation_ref:
                self.add_error(
                    "sanitisation_evidence_ref",
                    "Sanitisation evidence is required before disposal.",
                )
            if to_status == LifecycleStatus.DISPOSED and not disposal_ref:
                self.add_error(
                    "disposal_evidence_ref",
                    "Disposal evidence is required before disposal.",
                )
        if (
            to_status == LifecycleStatus.DISPOSED
            and not (
                cleaned_data.get("disposal_evidence_ref")
                or self.asset.disposal_evidence_ref
            )
        ):
            self.add_error(
                "disposal_evidence_ref",
                "Disposal evidence is required before disposal.",
            )
        return cleaned_data
