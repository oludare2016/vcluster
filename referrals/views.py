from decimal import Decimal

import requests
import logging
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .permissions import IsCompanyOrAdmin, IsAdmin
from .models import (
    Product,
    SupportTicket,
    UserRanking,
    Staff,
    TicketReply,
    ShareRequest,
)
from .serializers import (
    ProductSerializer,
    SupportTicketSerializer,
    UserRankingSerializer,
    VerifyAccountSerializer,
    StaffSerializer,
    SupportTicketReplySerializer,
)
from rest_framework import permissions
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from useraccounts.models import IndividualProfile, UserEarnings
from useraccounts.serializers import IndividualProfileSerializer

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Product model.
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            self.permission_classes = [IsCompanyOrAdmin]
        elif self.action in ["approve", "disapprove"]:
            self.permission_classes = [IsAdmin]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "admin":
            return Product.objects.all()
        elif user.user_type == "company":
            return Product.objects.filter(company=user)
        else:
            return Product.objects.all()  # Regular users can view all products

    def perform_create(self, serializer):
        serializer.save(company=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def approve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = "active"
        instance.save()
        return Response({"status": "Product approved"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def disapprove(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = "declined"
        instance.save()
        return Response({"status": "Product disapproved"}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class SupportTicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the SupportTicket model.
    """

    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the support tickets
        for the currently authenticated user.
        """
        user = self.request.user
        if user.is_staff:
            return SupportTicket.objects.all()
        return SupportTicket.objects.filter(submitted_by=user)


class SupportTicketReplyViewSet(viewsets.ModelViewSet):
    queryset = TicketReply.objects.all()
    serializer_class = SupportTicketReplySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TicketReply.objects.filter(replied_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer):
        serializer.save(replied_by=self.request.user)

    # Override update and partial_update to ensure replied_by isn't changed
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_update(self, serializer):
        serializer.save(replied_by=serializer.instance.replied_by)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class UserRankingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the UserRanking model.
    """

    queryset = UserRanking.objects.all()
    serializer_class = UserRankingSerializer
    permission_classes = [IsAuthenticated]


class VerifyAccountView(GenericAPIView):
    """
    View for verifying an account.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = VerifyAccountSerializer

    def get(self, request):
        """
        Retrieves account information from an external API based on the provided account number and bank code.
        """
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        account_number = serializer.validated_data.get("account_number")
        bank_code = serializer.validated_data.get("bank_code")

        # Replace with your actual Bearer token and API URL
        headers = {
            "Authorization": "Bearer Your_Bearer_Token",
        }

        params = {
            "account_number": account_number,
            "bank_code": bank_code,
        }

        try:
            response = requests.get(
                "http://nubapi.test/api/verify", headers=headers, params=params
            )
            response.raise_for_status()  # Raises an HTTPError for bad responses
            data = response.json()

            return Response(
                {
                    "account_name": data["account_name"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "other_name": data["other_name"],
                    "account_number": data["account_number"],
                    "bank_code": data["bank_code"],
                    "bank_name": data["Bank_name"],
                }
            )
        except requests.RequestException as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StaffViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Staff model.
    """

    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """
        Saves the data from the serializer into the database.

        Args:
            serializer (Serializer): The serializer instance containing the data to be saved.

        Returns:
            None
        """
        serializer.save()

    def get_queryset(self):
        """
        Get all Staff objects from the database.

        Returns:
            QuerySet: A queryset containing all Staff objects.
        """
        return Staff.objects.all()


class ReferralIndividualProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows listing individual profiles.
    """

    queryset = IndividualProfile.objects.all()
    serializer_class = IndividualProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "admin":
            return IndividualProfile.objects.all()
        return IndividualProfile.objects.filter(user=user)


class ShareProductView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        product_id = request.data.get("product_id")
        user = request.user

        try:
            product = Product.objects.get(uuid=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        # Update the number of shares
        product.shares += 1
        product.save()

        # Calculate the bonus
        bonus_amount = Decimal("1000.00")

        # Create or update the promote and earn bonus entry
        individual_profile = IndividualProfile.objects.get(user=user)
        UserEarnings.objects.update_or_create(
            individual_profile=individual_profile,
            earnings_type="promote_and_earn_bonus",
            defaults={
                "amount": bonus_amount,
                "description": f"Promote and Earn Bonus for sharing {product.product_name}",
            },
        )

        return Response(
            {"message": "Product shared successfully", "bonus": bonus_amount}
        )


class ShareRequestView(APIView):
    """
    View for handling share requests.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        product_id = request.data.get("product_id")
        user = request.user

        try:
            product = Product.objects.get(uuid=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        ShareRequest.objects.create(user=user, product=product)

        return Response({"message": "Share request submitted successfully"})


class ShareApprovalView(APIView):
    """
    View for handling share requests.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        share_request_id = request.data.get("share_request_id")
        action = request.data.get("action")  # "approve" or "reject"

        try:
            share_request = ShareRequest.objects.get(id=share_request_id)
        except ShareRequest.DoesNotExist:
            return Response({"error": "Share request not found"}, status=404)

        if action == "approve":
            share_request.status = "approved"
            share_request.save()

            product = share_request.product
            product.shares += 1
            product.save()

            # Calculate the bonus
            bonus_amount = Decimal("1000.00")

            # Create or update the promote and earn bonus entry
            individual_profile = IndividualProfile.objects.get(user=share_request.user)
            UserEarnings.objects.update_or_create(
                individual_profile=individual_profile,
                earnings_type="promote_and_earn_bonus",
                defaults={
                    "amount": bonus_amount,
                    "description": f"Promote and Earn Bonus for sharing {product.product_name}",
                },
            )

            return Response(
                {"message": "Share request approved", "bonus": bonus_amount}
            )

        elif action == "reject":
            share_request.status = "rejected"
            share_request.save()

            return Response({"message": "Share request rejected"})

        else:
            return Response({"error": "Invalid action"}, status=400)
