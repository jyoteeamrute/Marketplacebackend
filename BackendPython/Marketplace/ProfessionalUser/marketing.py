import logging
import mimetypes

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timezone as dt_timezone  
from django.utils import timezone  
# now = timezone.now()


from ProfessionalUser.models import *
from ProfessionalUser.serializers import *

logger = logging.getLogger(__name__)


class AdvertiseCampaignCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            uploaded_file = request.FILES.get('content')
            if uploaded_file:
                mime_type, _ = mimetypes.guess_type(uploaded_file.name)
                if not mime_type or not (mime_type.startswith('image/') or mime_type.startswith('video/')):
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "Invalid file type. Only image and video files are allowed."
                    }, status=status.HTTP_200_OK)
            company_id = request.data.get('company')
            
            if not company_id:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Company ID is required."
                }, status=status.HTTP_200_OK)
            professional_user = request.user
            try:
                company = professional_user.company
                if company.id != int(company_id):
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "User is not associated with the provided company."
                    }, status=status.HTTP_200_OK)
            except AttributeError:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Associated company not found for this user."
                }, status=status.HTTP_200_OK)

            data = request.data.copy()
            data['company'] = company.id  
            preferences = request.data.get('preferences', [])

            if isinstance(preferences, str):
                preferences = [int(x.strip()) for x in preferences.split(',') if x.strip().isdigit()]
            elif isinstance(preferences, list):
                preferences = [int(x) if isinstance(x, str) and x.isdigit() else x for x in preferences]

            allowed_category_ids = list(professional_user.categories.values_list('id', flat=True))
            invalid_preferences = [x for x in preferences if x not in allowed_category_ids]
            if invalid_preferences:
                logger.warning(f"Invalid preferences from user {professional_user.id}: {invalid_preferences}")
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Invalid preferences selected: {invalid_preferences}. Please select valid categories only."
                }, status=status.HTTP_200_OK)

            data.setlist('preferences', preferences)
            serializer = AdvertiseCampaignSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Advertise campaign created successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateAdvertiseCampaignAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, campaign_id):
        try:
            try:
                campaign = AdvertiseCampaign.objects.get(id=campaign_id)
            except AdvertiseCampaign.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Campaign not found."
                }, status=status.HTTP_404_NOT_FOUND)
            professional_user = request.user
            if campaign.company != professional_user.company:
                return Response({
                    "statusCode": 403,
                    "status": False,
                    "message": "You are not authorized to update this campaign."
                }, status=status.HTTP_403_FORBIDDEN)
            uploaded_file = request.FILES.get('content')
            if uploaded_file:
                mime_type, _ = mimetypes.guess_type(uploaded_file.name)
                if not mime_type or not (mime_type.startswith('image/') or mime_type.startswith('video/')):
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "Invalid file type. Only image and video files are allowed."
                    }, status=status.HTTP_200_OK)
            data = request.data.copy()
            preferences = request.data.get('preferences', None)

            if preferences is not None:
                if isinstance(preferences, str):
                    preferences = [int(x.strip()) for x in preferences.split(',') if x.strip().isdigit()]
                elif isinstance(preferences, list):
                    preferences = [int(x) if isinstance(x, str) and x.isdigit() else x for x in preferences]

                allowed_category_ids = list(professional_user.categories.values_list('id', flat=True))
                invalid_preferences = [x for x in preferences if x not in allowed_category_ids]

                if invalid_preferences:
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": f"Invalid preferences selected: {invalid_preferences}. Please select valid categories only."
                    }, status=status.HTTP_200_OK)

                data.setlist('preferences', preferences)
            serializer = AdvertiseCampaignSerializer(campaign, data=data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Advertise campaign updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class AdvertiseCampaignListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            professional_user = request.user
            try:
                company = professional_user.company
            except AttributeError:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Associated company not found for this user."
                }, status=status.HTTP_200_OK)
            campaigns = AdvertiseCampaign.objects.filter(company=company)
            serializer = AdvertiseCampaignSerializer(campaigns, many=True)

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Advertise campaigns retrieved successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdImpressionAPIView(APIView):
    def post(self, request):
        campaign_id = request.data.get('campaign_id')

        if not campaign_id:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "Campaign ID is required."
                }, status=status.HTTP_200_OK
            )

        try:
            campaign = AdvertiseCampaign.objects.get(id=campaign_id)

            if campaign.bid_type.lower() != "cpm":
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "This is not a CPM campaign."
                    }, status=status.HTTP_200_OK
                )

            if campaign.last_updated.date() != timezone.now().date():
                campaign.today_impressions = 0
                campaign.last_updated = timezone.now()
                campaign.save()

            current_impressions = campaign.today_impressions
            next_total_impressions = current_impressions + 1
            cost_per_mille = float(campaign.max_bid or 0)
            predicted_cost = (next_total_impressions / 1000) * cost_per_mille
            daily_budget = float(campaign.daily_budget or 0)

            print("Predicted total cost with next impression:", predicted_cost)
            print("Daily budget:", daily_budget)

            if predicted_cost > daily_budget:
                raise ValidationError("CPM Daily budget exceeded.")

            campaign.today_impressions = next_total_impressions
            campaign.save()
            AdImpression.objects.create(campaign=campaign, user=request.user)

            total_impressions = campaign.impressions.count()
            total_cost = (total_impressions / 1000) * cost_per_mille
            cpm_data = {
                "total_impressions": total_impressions,
                "cost_per_mille": cost_per_mille,
                "total_cost": round(total_cost, 2)
            }

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Impression counted.",
                "data": cpm_data
            }, status=status.HTTP_200_OK)

        except AdvertiseCampaign.DoesNotExist:
            return Response(
                {
                    "statusCode": 404,
                    "status": False,
                    "message": "Campaign not found."
                }, status=status.HTTP_200_OK
            )

        except ValidationError as ve:
            return Response(
                {
                    "statusCode": 403,
                    "status": False,
                    "message": str(ve)
                }, status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "An unexpected error occurred.",
                    "error": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdClickAPIView(APIView):
    def post(self, request):
        campaign_id = request.data.get('campaign_id')
        if not campaign_id:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "Campaign ID is required."
                }, status=status.HTTP_200_OK
            )

        try:
            campaign = AdvertiseCampaign.objects.get(id=campaign_id)

            if campaign.bid_type.lower() != "cpc":
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "This is not a CPC campaign."
                    }, status=status.HTTP_200_OK
                )

            if campaign.last_updated.date() != timezone.now().date():
                campaign.today_clicks = 0
                campaign.last_updated = timezone.now()
                campaign.save()


            current_clicks = campaign.today_clicks
            next_click_cost = float(campaign.max_bid or 0)
            total_cost_if_clicked = (current_clicks + 1) * next_click_cost
            daily_budget = float(campaign.daily_budget or 0)

            print("Predicted total cost with next click:", total_cost_if_clicked)
            print("Daily budget:", daily_budget)

            if total_cost_if_clicked >= daily_budget:
                return Response(
                    {
                        "statusCode": 403,
                        "status": False,
                        "message": "CPC Daily budget exceeded."
                    }, status=status.HTTP_200_OK
                )

            campaign.today_clicks += 1
            campaign.save()

            AdClick.objects.create(campaign=campaign, user=request.user)
            total_clicks = campaign.clicks.count()
            total_cost = total_clicks * next_click_cost

            cpc_data = {
                "total_clicks": total_clicks,
                "cost_per_click": next_click_cost,
                "total_cost": round(total_cost, 2)
            }

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Click counted.",
                "data": cpc_data
            }, status=status.HTTP_200_OK)

        except AdvertiseCampaign.DoesNotExist:
            return Response(
                {
                    "statusCode": 404,
                    "status": False,
                    "message": "Campaign not found."
                }, status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "An unexpected error occurred.",
                    "error": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
            
class DeleteAdvertiseCampaignAPIView(APIView):
    def delete(self, request, campaign_id):
        try:
            campaign = AdvertiseCampaign.objects.get(id=campaign_id)

            if campaign.company != request.user.company:
                return Response({
                    "statusCode": 403,
                    "status": False,
                    "message": "You are not authorized to delete this campaign."
                }, status=status.HTTP_200_OK)
                
            campaign.delete()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Campaign deleted successfully."
            }, status=status.HTTP_200_OK)

        except AdvertiseCampaign.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Campaign not found."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while deleting the campaign.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
from django.utils import timezone  
class AdvertisingDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            professional_user = request.user

            try:
                company = professional_user.company
            except AttributeError:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "No company associated with this user."
                }, status=status.HTTP_200_OK)

            now = timezone.now()
            today = now.date()

            # Filter campaigns and clicks for this user's company
            active_campaigns_count = AdvertiseCampaign.objects.filter(
                company=company,
                startDateTime__lte=now,
                endDateTime__gte=now
            ).count()

            today_clicks = AdClick.objects.filter(
                campaign__company=company,
                timestamp__date=today
            ).count()

            total_campaigns = AdvertiseCampaign.objects.filter(company=company).count()

            campaign_history_display = (
                f"{total_campaigns/1000:.0f}k" if total_campaigns >= 1000 else str(total_campaigns)
            )

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Dashboard data fetched successfully.",
                "data": {
                    "active_campaigns": active_campaigns_count,
                    "performance_insights": today_clicks,
                    "campaign_history": campaign_history_display
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching dashboard data.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class CampaignPerformanceInsightsAPIView(APIView):
    def get(self, request):
        try:
            today = timezone.now().date()
            impressions_count = AdImpression.objects.filter(timestamp__date=today).count()
            clicks_count = AdClick.objects.filter(timestamp__date=today).count()
            conversions_count = AdConversion.objects.filter(timestamp__date=today).count()

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Campaign performance insights fetched successfully.",
                "data": {
                    "impressions": impressions_count,
                    "clicks": clicks_count,
                    "conversions": conversions_count,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching campaign performance data.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
