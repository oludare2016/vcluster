from django.utils.dateparse import parse_date
from rest_framework import viewsets, generics, permissions
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import IndividualProfile, CompanyProfile, UserEarnings, EarningsType
from .serializers import (
    IndividualProfileSerializer,
    CompanyProfileSerializer,
    CustomUserTokenObtainPairSerializer,
    SignupSerializer,
    PasswordResetSerializer,
    EarningsTypeSerializer,
)
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.core.mail import EmailMessage

User = get_user_model()


class SignupView(generics.CreateAPIView):
    """
    API endpoint that allows users to signup.
    """

    serializer_class = SignupSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        response_data = {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "user_type": user.user_type,
            "phone_number": user.phone_number,
            "address": user.address,
            "country": user.country,
            "state": user.state,
            "city": user.city,
            "date_joined": user.date_joined,
            "status": user.status,
            "profile_picture": (
                user.profile_picture.url if user.profile_picture else None
            ),
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        request = self.request
        sponsor_id = request.user.id if request.user.is_authenticated else None

        if user.user_type == "individual":
            profile = IndividualProfile.objects.get(user=user)
            response_data.update(
                {
                    "gender": profile.gender,
                    "sponsor_id": profile.sponsor_id,
                    "rank": profile.rank,
                    "total_earnings": profile.total_earnings,
                }
            )
        elif user.user_type == "company":
            profile = CompanyProfile.objects.get(user=user)
            response_data.update(
                {
                    "company_registration_number": profile.company_registration_number,
                }
            )

        return Response(response_data, status=status.HTTP_201_CREATED)


class IndividualProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = CompanyProfile.objects.all()
    serializer_class = IndividualProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "admin" or user.user_type == "individual":
            return IndividualProfile.objects.all()
        return IndividualProfile.objects.filter(user=user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class CompanyProfileViewSet(viewsets.ModelViewSet):
    queryset = CompanyProfile.objects.all()
    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == "admin" or user.user_type == "company":
            return CompanyProfile.objects.all()
        return CompanyProfile.objects.filter(user=user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom TokenObtainPairView
    """

    serializer_class = CustomUserTokenObtainPairSerializer


class UserEarningsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            profile = IndividualProfile.objects.get(user_id=user_id)
            earnings = UserEarnings.objects.filter(individual_profile=profile)

            # Get the date parameter from the request, default to today
            date_str = request.query_params.get("date")
            if date_str:
                selected_date = parse_date(date_str)
            else:
                selected_date = timezone.now().date()

            # Filter earnings by the selected date
            daily_earnings = earnings.filter(date=selected_date)

            monthly_earnings = {}
            for month in range(1, 13):
                total = (
                    earnings.filter(date__month=month).aggregate(Sum("amount"))[
                        "amount__sum"
                    ]
                    or 0
                )
                monthly_earnings[timezone.now().replace(month=month).strftime("%b")] = (
                    total
                )

            # Get all EarningsType objects
            earnings_types = EarningsType.objects.all()

            # Create a dictionary to store daily earnings for each type
            daily_earnings_by_type = {}
            for earnings_type in earnings_types:
                amount = (
                    daily_earnings.filter(earnings_type=earnings_type).aggregate(
                        Sum("amount")
                    )["amount__sum"]
                    or 0
                )
                daily_earnings_by_type[earnings_type.bonus_name] = amount

            data = {
                **daily_earnings_by_type,
                "monthly_earnings": monthly_earnings,
                "total_earnings": sum(earning.amount for earning in earnings),
                "selected_date_earnings": daily_earnings.aggregate(Sum("amount"))[
                    "amount__sum"
                ]
                or 0,
            }

            return Response(data)

        except IndividualProfile.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )


class PasswordResetRequestView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        if not email:
            return Response(
                {"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "No user found with this email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_site = get_current_site(request)
        mail_subject = "Reset your password"
        message = render_to_string(
            "useraccounts/password_reset_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(force_str(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )
        email = EmailMessage(mail_subject, message, to=[email])
        email.send()

        return Response(
            {"detail": "Password reset email sent."}, status=status.HTTP_200_OK
        )


class PasswordResetView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            uidb64 = kwargs.get("uidb64")
            token = kwargs.get("token")
            new_password = serializer.validated_data.get("new_password")

            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                user = None

            if user is not None and default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response(
                    {"detail": "Password has been reset."}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EarningTypesViewSet(viewsets.ModelViewSet):

    queryset = EarningsType.objects.all()
    serializer_class = EarningsTypeSerializer
    permission_classes = [IsAuthenticated]
