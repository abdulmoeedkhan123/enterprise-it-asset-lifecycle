from __future__ import annotations

from django import forms

from .models import (
    Asset,
    DisposalCase,
    LifecycleStatus,
    MaintenanceWorkOrder,
    ProcurementQuote,
    ProcurementRequest,
    ReturnWorkItem,
    SanitisationResult,
    SoftwareContract,
    SoftwareLicenseAssignment,
    SoftwareProduct,
)
from .services import ALLOWED_TRANSITIONS


ALLOWED_RETURN_WORK_ITEM_TRANSITIONS = {
    ReturnWorkItem.Status.OPEN: {ReturnWorkItem.Status.IN_PROGRESS},
    ReturnWorkItem.Status.IN_PROGRESS: {
        ReturnWorkItem.Status.OPEN,
        ReturnWorkItem.Status.CLOSED,
        ReturnWorkItem.Status.DISMISSED,
    },
    ReturnWorkItem.Status.CLOSED: {ReturnWorkItem.Status.OPEN},
    ReturnWorkItem.Status.DISMISSED: {ReturnWorkItem.Status.OPEN},
}


class ReturnWorkItemReviewForm(forms.Form):
    status = forms.ChoiceField(label="Update status")
    note = forms.CharField(
        max_length=255,
        label="Review note",
        widget=forms.TextInput(attrs={"placeholder": "Record the review outcome"}),
    )

    def __init__(self, *args, work_item, **kwargs):
        super().__init__(*args, **kwargs)
        choices = ALLOWED_RETURN_WORK_ITEM_TRANSITIONS.get(work_item.status, set())
        self.fields["status"].choices = [
            (status, status.replace("_", " ").title())
            for status in sorted(choices)
        ]

    def clean_note(self):
        note = self.cleaned_data["note"].strip()
        if not note:
            raise forms.ValidationError("Provide a note for this review action.")
        return note


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


class MaintenanceWorkOrderForm(forms.ModelForm):
    class Meta:
        model = MaintenanceWorkOrder
        fields = ("title", "description", "priority", "vendor", "target_date", "cost")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_cost(self):
        cost = self.cleaned_data.get("cost")
        if cost is not None and cost < 0:
            raise forms.ValidationError("Cost cannot be negative.")
        return cost


ALLOWED_WORK_ORDER_TRANSITIONS = {
    MaintenanceWorkOrder.Status.OPEN: {
        MaintenanceWorkOrder.Status.IN_PROGRESS,
        MaintenanceWorkOrder.Status.CANCELLED,
    },
    MaintenanceWorkOrder.Status.IN_PROGRESS: {
        MaintenanceWorkOrder.Status.WAITING_PARTS,
        MaintenanceWorkOrder.Status.COMPLETED,
        MaintenanceWorkOrder.Status.CANCELLED,
    },
    MaintenanceWorkOrder.Status.WAITING_PARTS: {
        MaintenanceWorkOrder.Status.IN_PROGRESS,
        MaintenanceWorkOrder.Status.CANCELLED,
    },
}


class MaintenanceStatusForm(forms.Form):
    status = forms.ChoiceField(label="Update status")

    def __init__(self, *args, work_order: MaintenanceWorkOrder, **kwargs):
        super().__init__(*args, **kwargs)
        valid_statuses = ALLOWED_WORK_ORDER_TRANSITIONS.get(work_order.status, set())
        self.fields["status"].choices = [
            (status, MaintenanceWorkOrder.Status(status).label)
            for status in sorted(valid_statuses)
        ]


class ProcurementRequestForm(forms.ModelForm):
    class Meta:
        model = ProcurementRequest
        fields = ("title", "description", "justification", "quantity", "required_by")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "justification": forms.Textarea(attrs={"rows": 3}),
            "required_by": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least one.")
        return quantity


class ProcurementQuoteForm(forms.ModelForm):
    class Meta:
        model = ProcurementQuote
        fields = ("supplier", "quote_reference", "unit_cost", "delivery_days", "notes")

    def clean_unit_cost(self):
        unit_cost = self.cleaned_data["unit_cost"]
        if unit_cost <= 0:
            raise forms.ValidationError("Quoted unit cost must be greater than zero.")
        return unit_cost


class ProcurementDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(("approve", "Approve"), ("reject", "Reject"))
    )
    note = forms.CharField(max_length=255, required=False)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("decision") == "reject" and not cleaned_data.get("note", "").strip():
            self.add_error("note", "Provide a reason when rejecting a request.")
        return cleaned_data


class PurchaseOrderForm(forms.Form):
    purchase_order_reference = forms.CharField(max_length=64)
    expected_delivery_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    tracking_reference = forms.CharField(max_length=64, required=False)


class ProcurementDeliveryUpdateForm(forms.Form):
    delivery_status = forms.ChoiceField(
        choices=(
            (ProcurementRequest.DeliveryStatus.IN_TRANSIT, "In transit"),
            (ProcurementRequest.DeliveryStatus.DELAYED, "Delayed"),
        )
    )
    expected_delivery_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    tracking_reference = forms.CharField(max_length=64, required=False)


class ProcurementReceiptForm(forms.Form):
    quantity = forms.IntegerField(min_value=1)
    receipt_reference = forms.CharField(max_length=64)


class DisposalRequestForm(forms.ModelForm):
    class Meta:
        model = DisposalCase
        fields = (
            "reason",
            "method",
            "sanitisation_result",
            "sanitisation_evidence_ref",
        )
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, asset: Asset, **kwargs):
        super().__init__(*args, **kwargs)
        self.asset = asset
        if not asset.sanitisation_required:
            self.fields["sanitisation_result"].required = False
            self.fields["sanitisation_evidence_ref"].required = False
            self.fields["sanitisation_result"].help_text = (
                "Optional because this asset is not marked for sanitisation."
            )
            self.fields["sanitisation_evidence_ref"].help_text = (
                "Optional because this asset is not marked for sanitisation."
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.asset.sanitisation_required:
            if cleaned_data.get("sanitisation_result") != SanitisationResult.PASSED:
                self.add_error(
                    "sanitisation_result",
                    "Passed sanitisation is required before requesting disposal.",
                )
            if not cleaned_data.get("sanitisation_evidence_ref", "").strip():
                self.add_error(
                    "sanitisation_evidence_ref",
                    "Sanitisation evidence is required before requesting disposal.",
                )
        return cleaned_data


class DisposalReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(("approve", "Approve"), ("reject", "Reject"))
    )
    note = forms.CharField(max_length=255, required=False)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("decision") == "reject" and not cleaned_data.get("note", "").strip():
            self.add_error("note", "Provide a reason when rejecting a disposal.")
        return cleaned_data


class DisposalCompletionForm(forms.Form):
    disposal_evidence_ref = forms.CharField(max_length=64)


class SoftwareProductForm(forms.ModelForm):
    class Meta:
        model = SoftwareProduct
        fields = ("name", "publisher", "version", "category", "description", "end_of_support")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "end_of_support": forms.DateInput(attrs={"type": "date"}),
        }


class SoftwareContractForm(forms.ModelForm):
    class Meta:
        model = SoftwareContract
        fields = (
            "supplier",
            "contract_reference",
            "contract_type",
            "license_metric",
            "purchased_quantity",
            "start_date",
            "end_date",
            "renewal_notice_days",
            "auto_renew",
            "annual_cost",
            "currency",
            "document_reference",
            "renewal_of",
            "notes",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, product: SoftwareProduct, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        self.fields["renewal_of"].queryset = product.contracts.exclude(
            status__in=[
                SoftwareContract.Status.CANCELLED,
                SoftwareContract.Status.RENEWED,
            ]
        )
        self.fields["renewal_of"].required = False
        self.fields["renewal_of"].help_text = (
            "Select the previous contract when recording a renewal."
        )

    def clean_purchased_quantity(self):
        quantity = self.cleaned_data["purchased_quantity"]
        if quantity < 1:
            raise forms.ValidationError("Purchased quantity must be at least one.")
        return quantity

    def clean_renewal_notice_days(self):
        days = self.cleaned_data["renewal_notice_days"]
        if days > 365:
            raise forms.ValidationError("Renewal notice must be no more than 365 days.")
        return days

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()


class SoftwareLicenseAssignmentForm(forms.ModelForm):
    class Meta:
        model = SoftwareLicenseAssignment
        fields = ("assignee_ref", "department", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean_assignee_ref(self):
        return self.cleaned_data["assignee_ref"].strip()
