from django.contrib import admin
from .models import SystemSetting, PaymentMethod, Task, Deposit, Withdraw, InvestmentPlan

# 1. System Settings Admin
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Ekbar settings create hole abar add korar dorkar nei, tai false rakha jay ba true rakha jay
        return not SystemSetting.objects.exists()

# 2. Payment Method & Deposit Numbers Admin
@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'is_active')
    list_editable = ('number', 'is_active')

# 3. Tasks Admin
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward', 'is_active')
    list_editable = ('reward', 'is_active')

# 4. Deposit Request Admin
@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'gateway', 'trx_id', 'status', 'created_at')
    list_filter = ('status', 'gateway', 'created_at')
    search_fields = ('user__username', 'trx_id')
    
    # অ্যাডমিন যখন স্ট্যাটাস 'Approved' করবে তখন ব্যালেন্স যোগ হওয়ার লজিক
    def save_model(self, request, obj, form, change):
        if change:
            # আগের ডাটাবেজের স্ট্যাটাস চেক করা
            old_obj = Deposit.objects.get(pk=obj.pk)
            if old_obj.status != 'Approved' and obj.status == 'Approved':
                # ইউজার প্রফাইল থেকে ব্যালেন্স বাড়িয়ে দেওয়া
                profile, created = UserProfile.objects.get_or_create(user=obj.user)
                profile.balance += obj.amount
                profile.save()
        super().save_model(request, obj, form, change)
# 5. Withdraw Request Admin
@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'method', 'account_number', 'status', 'created_at')
    list_filter = ('status',)

# 6. Investment Plans Admin
@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'daily_income', 'validity_days')