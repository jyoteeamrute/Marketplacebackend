from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import LoyaltyCard, Product
from ProfessionalUser.serializers import LoyaltyCardCreateSerializer


class CreateLoyaltyCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            product_id = request.data.get("product")

            if not product_id:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Product ID is required."
                }, status=status.HTTP_200_OK)

            # Fetch the product only if it belongs to the logged-in user's company
            user_company = request.user.company
            try:
                product = Product.objects.get(id=product_id, company=user_company)
            except Product.DoesNotExist:
                return Response({
                    "statusCode": 403,
                    "status": False,
                    "message": "You are not authorized to create a loyalty card for this product."
                }, status=status.HTTP_200_OK)

            existing_loyalty_count = LoyaltyCard.objects.filter(company=user_company).count()
            if existing_loyalty_count >= 10:
                return Response({
                    "statusCode": 403,
                    "status": False,
                    "message": "You have reached the maximum limit of 10 loyalty cards."
                }, status=status.HTTP_200_OK)
                
            # Prepare data for serializer
            data = request.data.copy()
            data["company"] = user_company.id

            serializer = LoyaltyCardCreateSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Loyalty Card created successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid data.",
                "errors": serializer.errors
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Validation error.",
                "errors": str(e)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class GetLoyaltyCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            company = request.user.company
            loyalty_cards = LoyaltyCard.objects.filter(company=company)

            serializer = LoyaltyCardCreateSerializer(loyalty_cards, many=True)
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Loyalty cards fetched successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
            
class UpdateLoyaltyCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            company = request.user.company

            # Fetch the loyalty card ensuring it belongs to user's company
            loyalty_card = get_object_or_404(LoyaltyCard, pk=pk, company=company)

            data = request.data.copy()
            data["company"] = company.id  # Ensure company is not changed

            serializer = LoyaltyCardCreateSerializer(loyalty_card, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Loyalty Card updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid data.",
                "errors": serializer.errors
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeleteLoyaltyCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            company = request.user.company

            # Ensure the loyalty card belongs to the user's company
            loyalty_card = get_object_or_404(LoyaltyCard, pk=pk, company=company)

            loyalty_card.delete()

            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Loyalty Card deleted successfully."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)