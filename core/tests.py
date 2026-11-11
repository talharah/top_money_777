from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Deposit, InvestmentPlan, PaymentMethod, ReferralCommission, SupportTicket,
    SystemSetting, Task, TaskSubmission, UserInvestment, UserProfile, Withdraw,
)


class PlatformTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user-1', password='safe-test-password')
        self.profile = UserProfile.objects.create(
            user=self.user, balance=Decimal('500.00')
        )
        self.admin_user = User.objects.create_superuser(
            username='admin-1', email='admin@example.test', password='safe-admin-password'
        )
        self.factory = RequestFactory()
        SystemSetting.objects.create(
            pk=1,
            min_deposit=Decimal('350.00'),
            min_withdraw=Decimal('110.00'),
            withdraw_fee=10,
        )
        self.client.force_login(self.user)

    def save_admin_model(self, model, obj, change=True):
        request = self.factory.post('/admin/')
        request.user = self.admin_user
        admin.site._registry[model].save_model(request, obj, form=None, change=change)


class DailyCheckinViewTests(PlatformTestCase):
    def test_claim_adds_reward_to_main_balance(self):
        self.profile.balance = Decimal('12.35')
        self.profile.save(update_fields=['balance'])

        response = self.client.post(reverse('daily_checkin'))

        self.profile.refresh_from_db()
        self.assertRedirects(response, reverse('index'))
        self.assertEqual(self.profile.balance, Decimal('17.35'))
        self.assertIsNotNone(self.profile.last_check_in)

    def test_claim_within_24_hours_does_not_add_reward_again(self):
        self.client.post(reverse('daily_checkin'))
        self.profile.refresh_from_db()
        claimed_balance = self.profile.balance

        response = self.client.post(reverse('daily_checkin'))

        self.profile.refresh_from_db()
        self.assertRedirects(response, reverse('index'))
        self.assertEqual(self.profile.balance, claimed_balance)

    def test_claim_requires_post(self):
        response = self.client.get(reverse('daily_checkin'))

        self.profile.refresh_from_db()
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.profile.balance, Decimal('500.00'))


class RegistrationAndReferralTests(PlatformTestCase):
    def test_registration_adds_welcome_bonus_and_links_referrer(self):
        self.client.logout()

        response = self.client.post(reverse('register'), {
            'fullname': 'New User',
            'phone': '01712345678',
            'password': 'Complex-test-pass-934!',
            'confirm_password': 'Complex-test-pass-934!',
            'referral_code': self.profile.referral_code,
        })

        self.assertRedirects(response, reverse('login'))
        new_profile = UserProfile.objects.get(user__username='01712345678')
        self.assertEqual(new_profile.balance, Decimal('15.00'))
        self.assertEqual(new_profile.referred_by, self.profile)

    def test_referral_dashboard_shows_real_counts_and_commission(self):
        invited = User.objects.create_user(username='invited', password='safe-test-password')
        UserProfile.objects.create(user=invited, referred_by=self.profile)
        ReferralCommission.objects.create(
            deposit=Deposit.objects.create(
                user=invited,
                amount=Decimal('350.00'),
                gateway='bkash',
                trx_id='REF-TRX-1',
                status=Deposit.Status.APPROVED,
                balance_credited=True,
            ),
            recipient=self.profile,
            referred_profile=invited.userprofile,
            level=1,
            rate_percent=Decimal('10.00'),
            amount=Decimal('35.00'),
        )

        response = self.client.get(reverse('refer'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['referral_count'], 1)
        self.assertEqual(response.context['referral_earnings'], Decimal('35.00'))
        self.assertIn(self.profile.referral_code, response.context['referral_link'])


class DepositAndWithdrawalTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        PaymentMethod.objects.create(name='bkash', number='01700000000')

    def test_deposit_request_persists_sender_and_waits_for_admin_approval(self):
        response = self.client.post(reverse('deposit'), {
            'amount': '350.00',
            'gateway': 'bkash',
            'sender_number': '01711111111',
            'trx_id': 'trx-abc-1',
        })

        deposit = Deposit.objects.get(trx_id='TRX-ABC-1')
        self.profile.refresh_from_db()
        self.assertRedirects(response, reverse('index'))
        self.assertEqual(deposit.sender_number, '01711111111')
        self.assertEqual(deposit.status, Deposit.Status.PENDING)
        self.assertEqual(self.profile.balance, Decimal('500.00'))

    def test_deposit_rejects_below_minimum_and_duplicate_transaction_id(self):
        response = self.client.post(reverse('deposit'), {
            'amount': '100',
            'gateway': 'bkash',
            'sender_number': '01711111111',
            'trx_id': 'same-id',
        })
        self.assertRedirects(response, reverse('deposit'))
        self.assertFalse(Deposit.objects.exists())

        Deposit.objects.create(
            user=self.user, amount=Decimal('350'), gateway='bkash',
            sender_number='01711111111', trx_id='SAME-ID',
        )
        self.client.post(reverse('deposit'), {
            'amount': '350',
            'gateway': 'bkash',
            'sender_number': '01711111111',
            'trx_id': 'same-id',
        })
        self.assertEqual(Deposit.objects.count(), 1)

    def test_admin_approval_credits_deposit_and_two_referral_levels_once(self):
        second_user = User.objects.create_user(username='ref-level-2', password='safe-test-password')
        second_profile = UserProfile.objects.create(user=second_user, balance=Decimal('0.00'))
        direct_user = User.objects.create_user(username='ref-level-1', password='safe-test-password')
        direct_profile = UserProfile.objects.create(
            user=direct_user, balance=Decimal('0.00'), referred_by=second_profile
        )
        self.profile.referred_by = direct_profile
        self.profile.save(update_fields=['referred_by'])
        deposit = Deposit.objects.create(
            user=self.user,
            amount=Decimal('500.00'),
            gateway='bkash',
            trx_id='APPROVE-ONCE',
        )

        deposit.status = Deposit.Status.APPROVED
        self.save_admin_model(Deposit, deposit)
        deposit.refresh_from_db()
        self.profile.refresh_from_db()
        direct_profile.refresh_from_db()
        second_profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('1000.00'))
        self.assertEqual(direct_profile.balance, Decimal('50.00'))
        self.assertEqual(second_profile.balance, Decimal('15.00'))
        self.assertTrue(deposit.balance_credited)
        self.assertEqual(ReferralCommission.objects.filter(deposit=deposit).count(), 2)

        self.save_admin_model(Deposit, deposit)
        self.profile.refresh_from_db()
        direct_profile.refresh_from_db()
        second_profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('1000.00'))
        self.assertEqual(direct_profile.balance, Decimal('50.00'))
        self.assertEqual(second_profile.balance, Decimal('15.00'))

    def request_withdrawal(self, amount='200.00'):
        return self.client.post(reverse('withdraw'), {
            'amount': amount,
            'gateway': 'bKash',
            'receiver_number': '01722222222',
            'account_type': 'Personal',
        })

    def test_withdrawal_reserves_balance_and_rejection_refunds_once(self):
        response = self.request_withdrawal()
        withdrawal = Withdraw.objects.get()
        self.profile.refresh_from_db()
        self.assertRedirects(response, reverse('index'))
        self.assertEqual(self.profile.balance, Decimal('300.00'))
        self.assertEqual(withdrawal.account_number, '01722222222')
        self.assertEqual(withdrawal.fee_amount, Decimal('20.00'))
        self.assertEqual(withdrawal.payout_amount, Decimal('180.00'))
        self.assertTrue(withdrawal.balance_reserved)

        withdrawal.status = Withdraw.Status.REJECTED
        self.save_admin_model(Withdraw, withdrawal)
        withdrawal.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('500.00'))
        self.assertFalse(withdrawal.balance_reserved)

        self.save_admin_model(Withdraw, withdrawal)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('500.00'))

    def test_withdrawal_rejects_insufficient_balance_and_invalid_minimum(self):
        self.assertRedirects(self.request_withdrawal('600'), reverse('withdraw'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('500.00'))
        self.assertFalse(Withdraw.objects.exists())

        self.assertRedirects(self.request_withdrawal('100'), reverse('withdraw'))
        self.assertFalse(Withdraw.objects.exists())

    def test_approved_withdrawal_does_not_charge_balance_twice(self):
        self.request_withdrawal()
        withdrawal = Withdraw.objects.get()
        withdrawal.status = Withdraw.Status.APPROVED
        self.save_admin_model(Withdraw, withdrawal)

        self.profile.refresh_from_db()
        withdrawal.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('300.00'))
        self.assertFalse(withdrawal.balance_reserved)


class AdminWorkflowTests(PlatformTestCase):
    def test_admin_deposit_change_form_credits_pending_deposit(self):
        deposit = Deposit.objects.create(
            user=self.user, amount=Decimal('350.00'), gateway='bkash',
            sender_number='01711111111', trx_id='ADMIN-APPROVAL',
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin:core_deposit_change', args=[deposit.pk]),
            {
                'user': self.user.pk,
                'amount': '350.00',
                'gateway': 'bkash',
                'sender_number': '01711111111',
                'trx_id': 'ADMIN-APPROVAL',
                'status': Deposit.Status.APPROVED,
                '_save': 'Save',
            },
        )

        deposit.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(deposit.status, Deposit.Status.APPROVED)
        self.assertTrue(deposit.balance_credited)
        self.assertEqual(self.profile.balance, Decimal('850.00'))


class InvestmentAndTaskTests(PlatformTestCase):
    def test_plan_purchase_records_terms_and_income_claim_is_capped(self):
        plan = InvestmentPlan.objects.create(
            name='Basic',
            price=Decimal('300.00'),
            daily_income=Decimal('5.00'),
            validity_days=2,
        )
        response = self.client.post(reverse('plans'), {'plan_id': plan.pk})
        investment = UserInvestment.objects.get(profile=self.profile)
        self.profile.refresh_from_db()
        self.assertRedirects(response, reverse('plans'))
        self.assertEqual(self.profile.balance, Decimal('200.00'))
        self.assertEqual(investment.plan_name, 'Basic')
        self.assertEqual(investment.validity_days, 2)

        self.client.post(reverse('claim_plan_income', args=[investment.pk]))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('200.00'))

        investment.last_claimed_at = timezone.now() - timedelta(hours=25)
        investment.save(update_fields=['last_claimed_at'])
        self.client.post(reverse('claim_plan_income', args=[investment.pk]))
        self.profile.refresh_from_db()
        investment.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('205.00'))
        self.assertEqual(investment.days_credited, 1)

        self.client.post(reverse('claim_plan_income', args=[investment.pk]))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('205.00'))

    def test_insufficient_balance_does_not_create_investment(self):
        plan = InvestmentPlan.objects.create(
            name='Expensive', price=Decimal('600.00'),
            daily_income=Decimal('5.00'), validity_days=10,
        )
        self.client.post(reverse('plans'), {'plan_id': plan.pk})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('500.00'))
        self.assertFalse(UserInvestment.objects.exists())

    def test_task_submissions_are_admin_approved_and_reward_is_idempotent(self):
        task = Task.objects.create(
            title='Follow channel', link='https://example.com/task',
            reward=Decimal('20.00'),
        )
        response = self.client.get(reverse('tasks'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.title)

        response = self.client.post(reverse('submit_task', args=[task.pk]), {
            'proof': 'https://example.com/proof',
        })
        submission = TaskSubmission.objects.get(user=self.user, task=task)
        self.assertRedirects(response, reverse('tasks'))
        self.assertEqual(submission.status, TaskSubmission.Status.PENDING)

        submission.status = TaskSubmission.Status.APPROVED
        self.save_admin_model(TaskSubmission, submission)
        submission.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('520.00'))
        self.assertTrue(submission.reward_credited)

        self.save_admin_model(TaskSubmission, submission)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, Decimal('520.00'))


class SupportAndHistoryTests(PlatformTestCase):
    def test_profile_saves_name_and_email_and_rejects_invalid_email(self):
        response = self.client.post(reverse('personal_info'), {
            'full_name': 'Updated User',
            'email': 'updated@example.test',
        })

        self.user.refresh_from_db()
        self.assertRedirects(response, reverse('personal_info'))
        self.assertEqual(self.user.first_name, 'Updated User')
        self.assertEqual(self.user.email, 'updated@example.test')

        response = self.client.post(reverse('personal_info'), {
            'full_name': 'Should Not Save',
            'email': 'not-an-email',
        })

        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.first_name, 'Updated User')
        self.assertEqual(self.user.email, 'updated@example.test')
        self.assertContains(response, 'সঠিক ইমেইল ঠিকানা লিখুন।')

    def test_vip_plan_image_is_rendered_and_stored(self):
        plan = InvestmentPlan.objects.create(
            name='Image plan',
            price=Decimal('100.00'),
            daily_income=Decimal('10.00'),
            validity_days=10,
        )
        try:
            plan.image.save(f'test-{uuid4().hex}.jpg', ContentFile(b'test image bytes'), save=True)
            response = self.client.get(reverse('plans'))

            self.assertContains(response, plan.image.url)
            self.assertTrue(plan.image.storage.exists(plan.image.name))
        finally:
            plan.image.delete(save=False)

    def test_dashboard_shows_recent_transactions_and_labels_vip_income(self):
        Deposit.objects.create(
            user=self.user, amount=Decimal('350.00'), gateway='bkash',
            trx_id='DASHBOARD-DEP',
        )
        Withdraw.objects.create(
            user=self.user, amount=Decimal('110.00'), method='bKash',
            account_number='01722222222',
        )

        response = self.client.get(reverse('index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recent_activity']), 2)
        self.assertContains(response, 'Deposit (bkash)')
        self.assertContains(response, 'Withdraw (bKash)')
        self.assertContains(response, 'VIP Earnings')
        self.assertNotContains(response, 'Get App')
        self.assertNotContains(response, 'Server Time')

    def test_vip_membership_badges_reflect_active_plan(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'Free Member')
        self.assertContains(self.client.get(reverse('profile')), 'No active VIP plan')

        plan = InvestmentPlan.objects.create(
            name='Badge plan',
            price=Decimal('100.00'),
            daily_income=Decimal('10.00'),
            validity_days=10,
        )
        UserInvestment.objects.create(
            profile=self.profile,
            plan=plan,
            plan_name=plan.name,
            price_paid=plan.price,
            daily_income=plan.daily_income,
            validity_days=plan.validity_days,
            last_claimed_at=timezone.now(),
        )

        self.assertContains(self.client.get(reverse('index')), 'VIP Member')
        self.assertContains(self.client.get(reverse('profile')), 'VIP Plan Active')

    def test_support_hides_unconfigured_links_and_uses_accurate_channel_labels(self):
        response = self.client.get(reverse('support'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'your_helpline')
        self.assertNotContains(response, 'your_group')
        self.assertNotContains(response, 'WhatsApp')

        setting = SystemSetting.objects.get(pk=1)
        setting.helpline_link = 'https://t.me/example_help'
        setting.official_group_link = 'https://t.me/example_group'
        setting.save(update_fields=['helpline_link', 'official_group_link'])
        response = self.client.get(reverse('support'))

        self.assertContains(response, 'Help Line')
        self.assertContains(response, 'Official Group')

    def test_support_ticket_is_saved_and_visible_to_admin(self):
        response = self.client.post(reverse('support'), {
            'subject': 'Account Issue',
            'message': 'Please help me update my account details.',
        })

        self.assertRedirects(response, reverse('support'))
        ticket = SupportTicket.objects.get(user=self.user)
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)
        self.assertContains(self.client.get(reverse('support')), ticket.subject)

    def test_user_pages_and_admin_queues_render(self):
        self.assertEqual(self.client.get(reverse('index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('deposit')).status_code, 200)
        self.assertEqual(self.client.get(reverse('withdraw')).status_code, 200)
        self.client.force_login(self.admin_user)
        for route_name in (
            'admin:core_deposit_changelist',
            'admin:core_withdraw_changelist',
            'admin:core_tasksubmission_changelist',
            'admin:core_supportticket_changelist',
            'admin:core_referralcommission_changelist',
        ):
            with self.subTest(route=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

    def test_history_renders_real_deposits_and_withdrawals(self):
        Deposit.objects.create(
            user=self.user, amount=Decimal('350.00'), gateway='bkash',
            trx_id='HISTORY-DEP',
        )
        Withdraw.objects.create(
            user=self.user, amount=Decimal('110.00'), method='bKash',
            account_number='01722222222',
        )

        response = self.client.get(reverse('history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Deposit (bkash)')
        self.assertContains(response, 'Withdraw (bKash)')
        self.assertEqual(len(response.context['history_list']), 2)
