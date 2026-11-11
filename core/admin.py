from decimal import Decimal, ROUND_HALF_UP

from django.contrib import admin
from django.db import transaction

from .models import (
    Deposit, InvestmentPlan, PaymentMethod, ReferralCommission, SupportTicket,
    SystemSetting, Task, TaskSubmission, UserInvestment, UserProfile, Withdraw,
)


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return super().has_add_permission(request) and not SystemSetting.objects.exists()


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'is_active')
    list_editable = ('number', 'is_active')
    list_filter = ('is_active', 'name')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward', 'is_active')
    list_editable = ('reward', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title',)


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'gateway', 'sender_number', 'trx_id', 'status', 'created_at')
    list_filter = ('status', 'gateway', 'created_at')
    search_fields = ('user__username', 'trx_id', 'sender_number')
    readonly_fields = ('balance_credited', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status != Deposit.Status.PENDING:
            fields.extend(field.name for field in self.model._meta.fields if field.name not in fields)
        return fields

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                Deposit.objects.select_for_update().get(pk=obj.pk)
            super().save_model(request, obj, form, change)

            credited = False
            if obj.status == Deposit.Status.APPROVED:
                credited = Deposit.objects.filter(
                    pk=obj.pk,
                    status=Deposit.Status.APPROVED,
                    balance_credited=False,
                ).update(balance_credited=True)
            if credited:
                obj.balance_credited = True
                profile, _ = UserProfile.objects.get_or_create(user=obj.user)
                profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
                profile.balance += obj.amount
                profile.save(update_fields=['balance'])

                direct_referrer = profile.referred_by
                referral_levels = (
                    (direct_referrer, 1, Decimal('10.00')),
                    (direct_referrer.referred_by if direct_referrer else None, 2, Decimal('3.00')),
                )
                for recipient, level, rate in referral_levels:
                    if recipient is None:
                        continue
                    commission_amount = (
                        obj.amount * rate / Decimal('100')
                    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if commission_amount <= 0:
                        continue
                    commission, created = ReferralCommission.objects.get_or_create(
                        deposit=obj,
                        level=level,
                        defaults={
                            'recipient': recipient,
                            'referred_profile': profile,
                            'rate_percent': rate,
                            'amount': commission_amount,
                        },
                    )
                    if created:
                        recipient = UserProfile.objects.select_for_update().get(pk=recipient.pk)
                        recipient.balance += commission.amount
                        recipient.save(update_fields=['balance'])



@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'amount', 'fee_amount', 'payout_amount', 'method',
        'account_number', 'status', 'created_at',
    )
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('user__username', 'account_number')
    readonly_fields = ('balance_reserved', 'balance_refunded', 'fee_amount', 'payout_amount', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status != Withdraw.Status.PENDING:
            fields.extend(field.name for field in self.model._meta.fields if field.name not in fields)
        return fields

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                Withdraw.objects.select_for_update().get(pk=obj.pk)
            super().save_model(request, obj, form, change)
            if obj.status == Withdraw.Status.REJECTED:
                refunded = Withdraw.objects.filter(
                    pk=obj.pk,
                    status=Withdraw.Status.REJECTED,
                    balance_reserved=True,
                ).update(balance_reserved=False, balance_refunded=True)
            else:
                refunded = 0
            if refunded:
                profile = UserProfile.objects.select_for_update().get(user=obj.user)
                profile.balance += obj.amount
                profile.save(update_fields=['balance'])
                obj.balance_refunded = True
            elif obj.status == Withdraw.Status.APPROVED:
                Withdraw.objects.filter(
                    pk=obj.pk,
                    status=Withdraw.Status.APPROVED,
                    balance_reserved=True,
                ).update(balance_reserved=False)
            obj.refresh_from_db()


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'daily_income', 'validity_days')
    search_fields = ('name',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'balance', 'referral_code', 'referred_by')
    search_fields = ('user__username', 'phone_number', 'referral_code')
    list_select_related = ('user', 'referred_by')


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('profile', 'plan_name', 'price_paid', 'days_credited', 'validity_days', 'purchased_at')
    list_filter = ('plan', 'purchased_at')
    search_fields = ('profile__user__username', 'plan_name')
    readonly_fields = tuple(field.name for field in UserInvestment._meta.fields)


@admin.register(TaskSubmission)
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'reward_amount', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'task', 'created_at')
    search_fields = ('user__username', 'task__title', 'proof')
    readonly_fields = ('user', 'task', 'proof', 'reward_amount', 'reward_credited', 'created_at', 'updated_at')

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status != TaskSubmission.Status.PENDING:
            fields.append('status')
        return fields

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                TaskSubmission.objects.select_for_update().get(pk=obj.pk)
            super().save_model(request, obj, form, change)
            credited = 0
            if obj.status == TaskSubmission.Status.APPROVED:
                credited = TaskSubmission.objects.filter(
                    pk=obj.pk,
                    status=TaskSubmission.Status.APPROVED,
                    reward_credited=False,
                ).update(reward_credited=True)
            if credited:
                profile, _ = UserProfile.objects.get_or_create(user=obj.user)
                profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
                profile.balance += obj.reward_amount
                profile.save(update_fields=['balance'])
                obj.reward_credited = True


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'subject', 'message', 'admin_response')
    readonly_fields = ('user', 'subject', 'message', 'created_at', 'updated_at')


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'referred_profile', 'deposit', 'level', 'rate_percent', 'amount', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('recipient__user__username', 'referred_profile__user__username', 'deposit__trx_id')
    readonly_fields = tuple(field.name for field in ReferralCommission._meta.fields)
