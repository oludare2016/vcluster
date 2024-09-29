from django.urls import path

from .views import (
    DepositFunds,
    VerifyDeposit,
    WalletInfo,
    BankListView,
    ListDepositTransactions,
    VerifyBankAccountView,
    PayoutView,
    ValidateAccountView,
)


urlpatterns = [
    path("wallet_info/", WalletInfo.as_view()),
    path("deposit/", DepositFunds.as_view()),
    path("deposit/verify/<str:reference>/", VerifyDeposit.as_view()),
    path("banks/", BankListView.as_view(), name="bank-list"),
    path("transactions/", ListDepositTransactions.as_view()),
    path("verify_bank_account/", VerifyBankAccountView.as_view()),
    path("payout/", PayoutView.as_view(), name="payout"),
    path("validate-account/", ValidateAccountView.as_view(), name="validate-account"),
]
