import logging

from django.apps import apps
from django.conf import settings
from rest_framework import status
from django.db.models import Q
from rest_framework.views import APIView
from django.core.paginator import Paginator
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.contenttypes.models import ContentType

from Admin.models import *
from UserApp.utils import get_player_ids_by_user_id
from UserApp.models import Users
from UserApp.serializers import (
    UserSerializer,
    SupportOptionSerializer,
    UserRegistrationSerializer,
)
from ProfessionalUser.models import Friendship, CompanyDetails, ProfessionalUser

logger = logging.getLogger(__name__)

class GetUserProfileByBarcodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username=None):
        try:
            if username:
                try:
                    user = Users.objects.get(username__iexact=username)
                    serializer = UserRegistrationSerializer(user)
                    suggested_users = self.get_suggested_friends(request)
                    user_content_type = ContentType.objects.get_for_model(user)
                    profile_user = Users.objects.get(username__iexact=username)
                    current_user = request.user
                    user_content_types = ContentType.objects.get_for_model(Users)
                    serializer = UserRegistrationSerializer(profile_user)
                    friendship_request = Friendship.objects.filter(
                        Q(
                            sender_object_id=current_user.id,
                            sender_content_type=user_content_types,
                            receiver_object_id=profile_user.id,
                            receiver_content_type=user_content_types
                        ) |
                        Q(
                            sender_object_id=profile_user.id,
                            sender_content_type=user_content_types,
                            receiver_object_id=current_user.id,
                            receiver_content_type=user_content_types
                        ),
                        relationship_type="follow"
                    ).first()
                    request_id = friendship_request.id if friendship_request else ""
                    users_status = friendship_request.status if friendship_request else "follow"
                   
                    if friendship_request:
                        if friendship_request.status == "pending":
                            if friendship_request.sender_object_id == current_user.id:
                                users_status = "requested"
                            else:
                                users_status = "accept"
                        elif friendship_request.status in ["accepted", "message"]:
                            users_status = "message"
                        elif friendship_request.status == "declined":
                            users_status = "follow"
                    else:
                        users_status = "follow"
                    followers_count = Friendship.objects.filter(
                        receiver_object_id=user.id, 
                        receiver_content_type=user_content_type,
                        relationship_type="follow",
                    ).count()
                    following_count = Friendship.objects.filter(
                        sender_object_id=user.id,
                        sender_content_type=user_content_type,
                        relationship_type="follow",
                    ).count()

                    return Response(
                        {
                            "statusCode": 200,
                            "status": True,
                            "message": "User profile retrieved successfully",
                            "user": {
                                "requestid": request_id,
                                "status": users_status,
                                **serializer.data,
                                "following_count": following_count,
                                "followers_count": followers_count,
                                
                            },
                            "suggested_users": suggested_users
                        },
                        status=status.HTTP_200_OK
                    )
                except Users.DoesNotExist:
                    return Response(
                        {"statusCode": 404, "status": False, "message": "User not found"},
                        status=status.HTTP_200_OK
                    )
            users = Users.objects.all()
            serializer = UserRegistrationSerializer(users, many=True)

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "Users retrieved successfully",
                    "total_count": users.count(),
                    "users": serializer.data if users.exists() else []
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR  
            )
    
    def get_suggested_friends(self, request, query=""):
        try:
            current_user = request.user
            user_ct = ContentType.objects.get_for_model(current_user.__class__)
            company_ct = ContentType.objects.get_for_model(CompanyDetails)
            user_model_ct = ContentType.objects.get_for_model(Users)
            followed_companies = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=current_user.id,
                receiver_content_type=company_ct,
                relationship_type="follow",
                status="follow"
            ).values_list("receiver_object_id", flat=True)
            mutual_company_users = Friendship.objects.filter(
                receiver_content_type=company_ct,
                receiver_object_id__in=followed_companies,
                relationship_type="follow",
                status="follow"
            ).exclude(
                sender_object_id=current_user.id,
                sender_content_type=user_ct
            )
            followed_users = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=current_user.id,
                receiver_content_type=user_model_ct,
                relationship_type="follow"
            ).values_list("receiver_object_id", flat=True)

            second_degree_users = Friendship.objects.filter(
                sender_content_type=user_model_ct,
                sender_object_id__in=followed_users,
                receiver_content_type=user_model_ct,
                relationship_type="follow"
            ).exclude(
                receiver_object_id=current_user.id
            )
            all_suggested_user_ids = set(
                mutual_company_users.values_list("sender_object_id", flat=True)
            ).union(
                second_degree_users.values_list("receiver_object_id", flat=True)
            )

            existing_friend_ids = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=current_user.id,
                receiver_content_type=user_model_ct,
                relationship_type__in=["follow", "friend"]
            ).values_list("receiver_object_id", flat=True)

            final_suggested_ids = list(all_suggested_user_ids - set(existing_friend_ids) - {current_user.id})
            suggested_users_qs = Users.objects.filter(id__in=final_suggested_ids)

            if not suggested_users_qs.exists():
                suggested_users_qs = Users.objects.exclude(
                    id__in=list(existing_friend_ids) + [current_user.id]
                ).order_by('?')[:10]
            suggestions = []
            for user in suggested_users_qs:
                friendship = Friendship.objects.filter(
                    Q(
                        sender_object_id=current_user.id,
                        sender_content_type=user_model_ct,
                        receiver_object_id=user.id,
                        receiver_content_type=user_model_ct
                    ) |
                    Q(
                        sender_object_id=user.id,
                        sender_content_type=user_model_ct,
                        receiver_object_id=current_user.id,
                        receiver_content_type=user_model_ct
                    ),
                    relationship_type="follow"
                ).first()

                if friendship:
                    if friendship.status == "pending":
                        if friendship.sender_object_id == current_user.id:
                            status_label = "requested"
                        else:
                            status_label = "accept"
                    elif friendship.status in ["accepted", "message"]:
                        status_label = "message"
                    elif friendship.status == "declined":
                        status_label = "follow"
                    else:
                        status_label = friendship.status
                else:
                    status_label = "follow"

                suggestions.append({
                    "id": user.id,
                    "type": "users",
                    "username": user.username,
                    "email": user.email,
                    "firstName": user.firstName,
                    "lastName": user.lastName,
                    "profileImage": request.build_absolute_uri(user.profileImage.url) if user.profileImage else None,
                    "status": status_label
                })

            return suggestions

        except Exception as e:
            print(f"Error in getting suggested friends: {str(e)}")
            return []


class SearchUsersView(APIView):

    permission_classes = [IsAuthenticated]
    def get_follow_status(self, sender, receiver):
        print("::::::::::::")
        try:
            sender_ct = ContentType.objects.get_for_model(sender)
            receiver_ct = ContentType.objects.get_for_model(receiver)

            return Friendship.objects.filter(
                sender_content_type=sender_ct,
                sender_object_id=sender.id,
                receiver_content_type=receiver_ct,
                receiver_object_id=receiver.id,
                relationship_type="follow",
                status="follow"
            ).exists()
        except Exception as e:
            return False
    def get_relationship_status(self, sender, receiver):
        try:
            sender_ct = ContentType.objects.get_for_model(sender)
            receiver_ct = ContentType.objects.get_for_model(receiver)

            you_to_them = Friendship.objects.filter(
                sender_content_type=sender_ct,
                sender_object_id=sender.id,
                receiver_content_type=receiver_ct,
                receiver_object_id=receiver.id,
                relationship_type="follow"
            ).first()

            them_to_you = Friendship.objects.filter(
                sender_content_type=receiver_ct,
                sender_object_id=receiver.id,
                receiver_content_type=sender_ct,
                receiver_object_id=sender.id,
                relationship_type="follow"
            ).first()

            if you_to_them:
                if you_to_them.status == "pending":
                    return "requested", you_to_them.id
                elif you_to_them.status in ["accepted", "message"]:
                    return "message", you_to_them.id
                elif you_to_them.status == "declined":
                    return "follow", None
            if them_to_you:
                if them_to_you.status == "pending":
                    return "accept", them_to_you.id 
                elif them_to_you.status in ["accepted", "message"]:
                    return "message", them_to_you.id
                elif them_to_you.status == "declined":
                    return "follow", None
            return "follow", None

        except Exception as e:
            print(f"Relationship check error: {e}")
            return "follow", None


    def get_suggested_friends(self, request, query=""):
        try:
            user = request.user
            user_ct = ContentType.objects.get_for_model(user.__class__)
            company_ct = ContentType.objects.get_for_model(CompanyDetails)
            other_user_ct = ContentType.objects.get_for_model(Users)

            followed_companies = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=company_ct,
                relationship_type="follow",
            ).values_list("receiver_object_id", flat=True)

            matched_users = Friendship.objects.filter(
                receiver_content_type=company_ct,
                receiver_object_id__in=followed_companies,
                relationship_type="follow",
            ).exclude(
                sender_object_id=user.id,
                sender_content_type=user_ct
            )

            existing_friends_ids = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=other_user_ct,
                relationship_type__in=["follow", "friend"]
            ).values_list("receiver_object_id", flat=True)

            suggested_users_qs = Users.objects.filter(
                id__in=matched_users.values_list("sender_object_id", flat=True)
            ).exclude(id__in=existing_friends_ids).distinct()

            suggestions = []
            for u in suggested_users_qs:
                relationship_status, request_id = self.get_relationship_status(request.user, u)
                suggestions.append({
                    "id": u.id,
                    "type": "users",
                    "username": u.username,
                    "email": u.email,
                    "firstName": u.firstName,
                    "lastName": u.lastName,
                    "profileImage": request.build_absolute_uri(u.profileImage.url) if u.profileImage else None,
                    "status": relationship_status,
                    "request_id": request_id
                })

            return suggestions
        except Exception as e:
            print(f"Error in getting suggested friends: {str(e)}")
            return []
    def get(self, request):
       
        try:
            query = request.GET.get("query", "").strip()
            user_type = request.GET.get("userType", "all").lower()  
            page = int(request.GET.get("page", 1))
            per_page = int(request.GET.get("per_page", 10)) 

            users_qs = Users.objects.none()  
            professionals_qs = ProfessionalUser.objects.none() 
            companyDetails_qa=CompanyDetails.objects.none()
         
            if user_type in ["user", "all"]:
                users_qs = Users.objects.filter(
                    Q(username__icontains=query) | 
                    Q(firstName__icontains=query) | 
                    Q(lastName__icontains=query)
                ).exclude(id=request.user.id)  

            if user_type in ["professional", "all"]:
                professionals_qs = ProfessionalUser.objects.filter(
                    Q(userName__icontains=query) | 
                    Q(email__icontains=query)
                ).exclude(email=request.user.email) 
            if user_type in ["company", "all"]:
                companyDetails_qa = CompanyDetails.objects.filter(
                    Q(companyName__icontains=query) | 
                    Q(managerFullName__icontains=query) | 
                    Q(userName__icontains=query) | 
                    Q(email__icontains=query)
                )    
            all_users = list(users_qs) + list(professionals_qs) + list(companyDetails_qa)
            paginator = Paginator(all_users, per_page)
            users_page = paginator.get_page(page)

            users_data = []
            for user in users_page:
                relationship_status,request_id = self.get_relationship_status(request.user, user)
                if isinstance(user, Users):
                    users_data.append({
                        "id": user.id,
                        "type": "users",
                        "username": user.username,
                        "email": user.email,
                        "firstName": user.firstName,
                        "lastName": user.lastName,
                        "profileImage": request.build_absolute_uri(user.profileImage.url) if user.profileImage else None,
                        "status": relationship_status,
                        "request_id": request_id
                    })
                
            suggested_friends = self.get_suggested_friends(request, query)

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Users and company retrieved successfully.",
                "totalUsers": paginator.count,
                "totalPages": paginator.num_pages,
                "currentPage": page,
                "users": users_data,
                "suggestedFriends": suggested_friends
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error in user search: {str(e)}")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while processing your request.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


 
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def send_friend_and_follow_request(request):
    try:
        sender = request.user  
        receiver_id = request.data.get("receiverId")
        receiver_type = request.data.get("receiverType")  
        request_id = request.data.get('request_id')
        action = request.data.get("requestType", "friend") 
        if action in ["accept", "decline", "requested"] and request_id:
            try:
                friendship = Friendship.objects.get(id=request_id)
            except Friendship.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Friend/follow request not found."
                }, status=status.HTTP_200_OK)
 
            if action == "accept":
                friendship.status = "message"
                friendship.save()
                
                print("caeept666666666666666")
                if friendship.receiver_object_id:
                    receiver_user = Users.objects.get(id=friendship.receiver_object_id)
                    
                elif friendship.receiver_object_id:
                    receiver_user = ProfessionalUser.objects.get(id=friendship.receiver_object_id)
                    
                get_player_ids_by_user_id(friendship.sender_object_id, content = f"{receiver_user.username} accepted your request.")
                
                print("accepted")
                
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Request accepted. Now you can message.",
                    "friendshipId": friendship.id,
                    "status": friendship.status,
                    "updated_at": friendship.updated_at
                })
 
            elif action in ["decline", "requested"]:
                friendship_id = friendship.id
                friendship.delete()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Friend/follow request removed.",
                    "friendshipId": friendship_id
                })
        if not receiver_id or not receiver_type:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Receiver ID and type are required."
            })
 
        if receiver_type.lower() == "users" and str(receiver_id) == str(sender.id):
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Cannot send request to yourself."
            })
 
        receiver_model_map = {
            "users": Users,
            "professionaluser": ProfessionalUser,
            "company": CompanyDetails
        }
 
        model = receiver_model_map.get(receiver_type.lower())
        if not model:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": f"Invalid receiver type: {receiver_type}"
            })
 
        try:
            receiver = model.objects.get(id=receiver_id)
        except model.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": f"{model.__name__} not found."
            })
 
        receiver_ct = ContentType.objects.get_for_model(model)
        existing = Friendship.objects.filter(
            sender_content_type=ContentType.objects.get_for_model(sender),
            sender_object_id=sender.id,
            receiver_content_type=receiver_ct,
            receiver_object_id=receiver_id,
            relationship_type="follow"  
        ).exclude(status="declined").first()
 
        if existing:
            if existing.status == "pending":
                friendship_id = existing.id
                existing.delete()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Friend/follow request cancelled.",
                    "friendshipId": friendship_id
                })
 
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Friend/follow request already exists."
            })
        initial_status = "message" if receiver_ct.model == "companydetails" else "pending"
        

 
        friendship = Friendship.objects.create(
            sender_content_type=ContentType.objects.get_for_model(sender),
            sender_object_id=sender.id,
            receiver_content_type=receiver_ct,
            receiver_object_id=receiver_id,
            relationship_type="follow",
            status=initial_status
        )

        if friendship.sender_object_id:
            sender_user = Users.objects.get(id=friendship.sender_object_id)
                    
        elif friendship.sender_object_id:
            sender_user = ProfessionalUser.objects.get(id=friendship.sender_object_id)
        
        get_player_ids_by_user_id(
            friendship.receiver_object_id,  
            content = f"{sender_user.username}  sent you a follow request"
            )
        
        return Response({
            "statusCode": 201,
            "status": True,
            "message": "Request sent successfully.",
            "friendshipId": friendship.id,
            "status": friendship.status,
            "created_at": friendship.created_at
        })
 
    except Exception as e:
        print(f"Error sending request: {str(e)}")
        return Response({
            "statusCode": 500,
            "status": False,
            "message": "An error occurred while processing your request.",
            "error": str(e)
        })
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_friend_request(request):
    """
    Update an existing friend request. Actions: 'accept', 'decline', 'unfollow'.
    """
    try:
        request_id = request.data.get("requestId")
        action = request.data.get("action")  

        if not request_id or not action:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Request ID and action are required."
            }, status=status.HTTP_200_OK)

        friendship = Friendship.objects.get(id=request_id)
        if request.user.id not in [friendship.sender_object_id, friendship.receiver_object_id]:
            return Response({
                "statusCode": 403,
                "status": False,
                "message": "You are not authorized to update this request."
            }, status=status.HTTP_200_OK)

        if action == "accept":
            if friendship.status == "pending":
                friendship.status = "accepted"
                friendship.save()
                message = "Friend request accepted."
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Friend request is not pending."
                }, status=status.HTTP_200_OK)

        elif action == "decline":
            if friendship.status == "pending":
                friendship.status = "declined"
                friendship.save()
                message = "Friend request declined."
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Friend request is not pending."
                }, status=status.HTTP_200_OK)

        elif action == "unfollow":
            if friendship.status == "accepted":
                friendship.delete()
                message = "Unfollowed successfully."
            else:
                return Response({
                    "statusCode":400,
                    "status": False,
                    "message": "You can only unfollow accepted friends."
                }, status=status.HTTP_200_OK)

        else:
            return Response({
                "statusCode":200,
                "status": False,
                "message": "Invalid action. Use 'accept', 'decline', or 'unfollow'."
            }, status=status.HTTP_200_OK)

        return Response({
            "statusCode": status.HTTP_200_OK,
            "status": True,
            "message": message
        }, status=status.HTTP_200_OK)

    except Friendship.DoesNotExist:
        return Response({
            "statusCode": 404,
            "status": False,
            "message": "Friend request not found."
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "statusCode": 500,
            "status": False,
            "message": "An error occurred while processing your request.",
            "error": str(e)
        }, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def unfollow_professional_users(request):
    """
    Follow or unfollow a user/professional user.
    """
    try:
        user=request.user
        print("userrrrrrr",user)
        request_id = request.data.get("requestId")
        action = request.data.get("action") 

        if not request_id or not action:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Request ID and action are required."
            }, status=status.HTTP_200_OK)

        friendship = Friendship.objects.get(id=request_id)
        if request.user.id not in [friendship.sender_object_id, friendship.receiver_object_id]:
            return Response({
                "statusCode": 403,
                "status": False,
                "message": "You are not authorized to update this request."
            }, status=status.HTTP_200_OK)

        if action == "follow":
            friendship.status = "followed"
            friendship.save()
            message = "Followed successfully."

        elif action == "unfollow":
            friendship.status = "unfollow"
            friendship.save()
            message = "Unfollowed successfully."

        else:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid action. Use 'follow' or 'unfollow'."
            }, status=status.HTTP_200_OK)

        return Response({
            "statusCode": 200,
            "status": True,
            "message": message
        }, status=status.HTTP_200_OK)

    except Friendship.DoesNotExist:
        return Response({
            "statusCode": 404,
            "status": False,
            "message": "Follow request not found."
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "statusCode": 500,
            "status": False,
            "message": "An error occurred while processing your request.",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_list_requests(request):
    """
    Get a list of all pending friend and follow requests for the authenticated user.
    """
    try:
        user_ct = ContentType.objects.get_for_model(request.user)
        pending_requests = Friendship.objects.filter(
            receiver_content_type=user_ct,
            receiver_object_id=request.user.id,
            status="pending"
        )
        
        requests_data = []
        for req in pending_requests:
            try:
                sender = req.sender_content_type.get_object_for_this_type(id=req.sender_object_id)
                sender_data = {
                    "id": req.id,
                    "senderId": sender.id,
                    "senderName": sender.username if hasattr(sender, "username") else sender.userName,
                    "senderEmail": sender.email,
                    "senderPhone": sender.phone if hasattr(sender, "phone") else "N/A",
                    "relationshipType": req.relationship_type,
                    "status": req.status,
                    "created_at": req.created_at
                }
                requests_data.append(sender_data)
            except Users.DoesNotExist:
                continue
        
        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Pending friend requests retrieved successfully.",
            "totalRequests": len(requests_data),
            "requests": requests_data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            "statusCode": 500,
            "status": False,
            "message": f"An error occurred: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def respond_to_request(request):
    """
    Accept or Decline a friend request.
    """
    request_id = request.data.get("requestId")
    action = request.data.get("action")   

    if not request_id or action not in ["accept", "decline"]:
        return Response({
            "statusCode": 400,
            "status": False,
            "error": "Invalid request. Provide valid requestId and action (accept/decline)."
        }, status=status.HTTP_200_OK)

    try:
        friendship = Friendship.objects.get(id=request_id, receiver_object_id=request.user.id)

        friendship.status = "accepted" if action == "accept" else "declined"
        friendship.save()

        return Response({
            "statusCode": 200,
            "status": True,
            "message": f"Friend request has been {friendship.status} successfully."
        }, status=status.HTTP_200_OK)

    except Friendship.DoesNotExist:
        return Response({
            "statusCode": 404,
            "status": False,
            "error": "Request not found."
        }, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def friends_list(request):
    """
    Get a list of all accepted friends for the authenticated user.
    Returns total count and names of friends.
    """
    try:
        user_ct = ContentType.objects.get_for_model(request.user)

        sent_requests = Friendship.objects.filter(
            Q(status="accepted") | Q(status="message"),
            sender_content_type=user_ct,
            sender_object_id=request.user.id
        ).values_list("receiver_object_id", flat=True)

        received_requests = Friendship.objects.filter(
           Q(status="accepted") | Q(status="message"),
            receiver_content_type=user_ct,
            receiver_object_id=request.user.id
        ).values_list("sender_object_id", flat=True)
        friends_ids = list(sent_requests) + list(received_requests)
        friends_users = Users.objects.filter(id__in=friends_ids)
        total_friends = friends_users.count()
        friends_data = UserSerializer(friends_users, many=True).data

        return Response({
            "statusCode": 200,
            "status": True,
            "totalFriends": total_friends,
            "friends": friends_data
        }, status=status.HTTP_200_OK)

    except Users.DoesNotExist:
        return Response({
            "statusCode": 404,
            "status": False,
            "error": "Friends list not found."
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            "statusCode": 500,
            "status": False,
            "error": f"Something went wrong: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_following(request):
    """
    Get list of people the authenticated user is following professional users, with names and total count.
    """

    try:
        user_ct = ContentType.objects.get_for_model(request.user)

        following = Friendship.objects.filter(
            sender_content_type=user_ct,
            sender_object_id=request.user.id,
            relationship_type="follow",
            status="follow"
        )

        following_list = []
        for follow in following:
            try:
                receiver = follow.receiver_content_type.get_object_for_this_type(
                    id=follow.receiver_object_id
                )
                name = getattr(receiver, 'username', None) or getattr(receiver, 'userName', None)
                
                if not name:
                    continue  

                following_list.append({
                    "id": follow.receiver_object_id,
                    "name": name
                })
            except Exception as e:
                continue

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Following list retrieved successfully",
            "totalFollowing": len(following_list),
            "following": following_list
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "statusCode": 500,
            "status": False,
            "message": f"Something went wrong: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_followers(request):
    """
    Get a list of all users who follow the authenticated professional user.
    Returns total count and details of followers.
    """
    try:  
        user_ct = ContentType.objects.get_for_model(request.user)
        followers = Friendship.objects.filter(
            receiver_content_type=user_ct,
            receiver_object_id=request.user.id,
            relationship_type="follow",
            status="follow"
        ).values_list("sender_object_id", flat=True)
        if not followers:
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "No followers found.",
                "total_followers": 0,
                "followers": []
            }, status=status.HTTP_200_OK)
        follower_users = Users.objects.filter(id__in=followers)
        total_followers = follower_users.count()
        followers_data = UserSerializer(follower_users, many=True).data

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Followers retrieved successfully.",
            "total_followers": total_followers,
            "followers": followers_data
        }, status=status.HTTP_200_OK)


    except Exception as e:
        print(f"Error retrieving followers: {str(e)}")
        return Response({
            "statusCode": 500,
            "status": False,
            "message": "An error occurred while processing your request.",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_friends_status_list(request):
    """
    Get a list of all friendship requests sent by the authenticated user.
    Returns total count and request status (pending, accepted, declined).
    """
    try:
        user_ct = ContentType.objects.get_for_model(request.user)
        friend_requests = Friendship.objects.filter(
            sender_content_type=user_ct,
            sender_object_id=request.user.id
        ).values("receiver_object_id", "status", "relationship_type", "created_at", "receiver_content_type")
        if not friend_requests.exists():
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "No friend requests found.",
                "total_requests": 0,
                "requests": []
            }, status=status.HTTP_200_OK)
        request_data = []
        for req in friend_requests:
            receiver_id = req["receiver_object_id"]
            receiver_type_id = req["receiver_content_type"]
            receiver_ct_obj = ContentType.objects.get(id=receiver_type_id)
            print("receiver_ct_obj.model???",receiver_ct_obj.model)  
            if receiver_ct_obj.model == "users":
                try:
                    receiver = Users.objects.get(id=receiver_id)
                    receiver_name = receiver.username
                except Users.DoesNotExist:
                    receiver_name = "Unknown"
            elif receiver_ct_obj.model == "professionaluser":
                try:
                    receiver = ProfessionalUser.objects.get(id=receiver_id)
                    receiver_name = receiver.userName
                except ProfessionalUser.DoesNotExist:
                    receiver_name = "Unknown"
                  
            elif receiver_ct_obj.model == "companydetails":
                try:
                    receiver = CompanyDetails.objects.get(id=receiver_id)
                    receiver_name = receiver.companyName
                except CompanyDetails.DoesNotExist:
                    receiver_name = "Unknown"
            else:
                receiver_name = "Unknown"
            request_data.append({
                "receiverId": receiver_id,
                "receiverName": receiver_name,
                "status": req["status"],
                "relationshipType": req["relationship_type"],
                "requestedAt": req["created_at"]
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Friend requests retrieved successfully.",
            "totalRequests": len(request_data),
            "requests": request_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error retrieving friend requests: {str(e)}")
        return Response({
            "statusCode": 500,
            "status": False,
            "message": "An error occurred while processing your request.",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class SuggestedFriendsByCompany(APIView):
    permission_classes = [IsAuthenticated]

    def get_relationship_status(self, current_user, other_user):
        sender_ct = ContentType.objects.get_for_model(current_user.__class__)
        receiver_ct = ContentType.objects.get_for_model(other_user.__class__)

        friendship_request = Friendship.objects.filter(
            sender_content_type=sender_ct,
            sender_object_id=current_user.id,
            receiver_content_type=receiver_ct,
            receiver_object_id=other_user.id,
            relationship_type="follow"
        ).first()

        reverse_friendship = Friendship.objects.filter(
            sender_content_type=receiver_ct,
            sender_object_id=other_user.id,
            receiver_content_type=sender_ct,
            receiver_object_id=current_user.id,
            relationship_type="follow"
        ).first()

        if friendship_request:
            if friendship_request.status == "pending":
                return "requested"
            elif friendship_request.status in ["accepted", "message"]:
                return "message"
            elif friendship_request.status == "declined":
                return "follow"

        elif reverse_friendship:
            if reverse_friendship.status == "pending":
                return "accept"
            elif reverse_friendship.status in ["accepted", "message"]:
                return "message"
            elif reverse_friendship.status == "declined":
                return "follow"

        return "follow"

    def get(self, request):
        try:
            user = request.user
            user_ct = ContentType.objects.get_for_model(user.__class__)
            company_ct = ContentType.objects.get_for_model(CompanyDetails)
            user_model_ct = ContentType.objects.get_for_model(Users)
            followed_companies = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=company_ct,
                relationship_type="follow",
            ).values_list("receiver_object_id", flat=True)

            mutual_company_users = Friendship.objects.filter(
                receiver_content_type=company_ct,
                receiver_object_id__in=followed_companies,
                relationship_type="follow",
            ).exclude(
                sender_object_id=user.id,
                sender_content_type=user_ct
            )
            followed_users = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=user_model_ct,
                relationship_type="follow",
            ).values_list("receiver_object_id", flat=True)

            second_degree_users = Friendship.objects.filter(
                sender_content_type=user_model_ct,
                sender_object_id__in=followed_users,
                receiver_content_type=user_model_ct,
                relationship_type="follow",
            ).exclude(
                receiver_object_id=user.id
            )
            all_suggested_user_ids = set(
                mutual_company_users.values_list("sender_object_id", flat=True)
            ).union(
                second_degree_users.values_list("receiver_object_id", flat=True)
            )

            existing_friend_ids = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=user_model_ct,
                relationship_type__in=["follow", "friend"]
            ).values_list("receiver_object_id", flat=True)

            final_suggested_ids = list(all_suggested_user_ids - set(existing_friend_ids) - {user.id})

            suggested_users_qs = Users.objects.filter(id__in=final_suggested_ids)

            if not suggested_users_qs.exists():
                suggested_users_qs = Users.objects.exclude(
                    id__in=list(existing_friend_ids) + [user.id]
                ).order_by('?')[:10]

            suggestions = []
            for u in suggested_users_qs:
                status = self.get_relationship_status(user, u)
                suggestions.append({
                    "id": u.id,
                    "type": "users",
                    "username": u.username,
                    "email": u.email,
                    "firstName": u.firstName,
                    "lastName": u.lastName,
                    "profileImage": request.build_absolute_uri(u.profileImage.url) if u.profileImage else None,
                    "status": status
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Suggested friends based on mutual company or user follows.",
                "suggestedFriends": suggestions
            })

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "Something went wrong.",
                "error": str(e)
            })
       
   
class SupportOptionListView(ListAPIView):
    queryset = SupportOption.objects.all()
    serializer_class = SupportOptionSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": True,
            "statusCode":200,
            "message": "Support options fetched successfully",
            "data": serializer.data
        })
    

class MentionSuggestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"status": False, "message": "Query is required"}, status=400)

        user = request.user
        user_ct = ContentType.objects.get_for_model(user.__class__)
        friendships = Friendship.objects.filter(
            sender_content_type=user_ct,
            sender_object_id=user.id,
            relationship_type="follow",
            status="follow"
        )
        followed_user_ids = [
            f.receiver_object_id for f in friendships
            if f.receiver_content_type.model_class() == Users
        ]
        matched_users = Users.objects.filter(id__in=followed_user_ids, username__icontains=query)[:10]

        data = [
            {
                "username": u.username,
                "full_name": u.firstName,
                "profile_image": u.profileImage.url if hasattr(u, "profile") and u.profileImage else None
            }
            for u in matched_users
        ]

        return Response({
            "status": True,
            "message": "Mention suggestions fetched",
            "data": data
        }, status=200)
    



User = apps.get_model("UserApp", "Users")
ProfessionalUser = apps.get_model("ProfessionalUser", "ProfessionalUser")
Company = apps.get_model("ProfessionalUser", "CompanyDetails")
Friendship = apps.get_model("ProfessionalUser", "Friendship") 

from UserApp.models import PrivacySetting


class MentionableEntitiesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_user = request.user
        query = request.GET.get('query', '').lstrip('@').strip()

        try:
            current_user_ct = ContentType.objects.get_for_model(current_user)

            friendships = Friendship.objects.filter(
                Q(sender_content_type=current_user_ct, sender_object_id=current_user.id) |
                Q(receiver_content_type=current_user_ct, receiver_object_id=current_user.id),
                Q(status='accepted') | Q(status='follow')
            )

            mentionable_ids = {
                'Users': set(),
                'ProfessionalUser': set(),
                'CompanyDetails': set()
            }

            for f in friendships:
                if f.sender_object_id == current_user.id and f.sender_content_type == current_user_ct:
                    model_name = f.receiver_content_type.model_class().__name__
                    mentionable_ids.setdefault(model_name, set()).add(f.receiver_object_id)
                elif f.receiver_object_id == current_user.id and f.receiver_content_type == current_user_ct:
                    model_name = f.sender_content_type.model_class().__name__
                    mentionable_ids.setdefault(model_name, set()).add(f.sender_object_id)

            def safe_url(image_field):
                if not image_field:
                    return None
                if hasattr(image_field, 'url'):
                    url = image_field.url
                    if not url.startswith('http'):
                        return request.build_absolute_uri(url)
                    return url
                if not image_field.startswith('http'):
                    return f'https:/{settings.MEDIA_URL}{image_field}'
                return image_field

            def filter_users():
                return User.objects.filter(
                    id__in=mentionable_ids['Users'],
                    username__icontains=query
                ).values('id', 'firstName', 'lastName', 'profileImage', 'username')

            def filter_professionals():
                return ProfessionalUser.objects.select_related('company').filter(
                    id__in=mentionable_ids['ProfessionalUser'],
                    userName__icontains=query
                ).values(
                    'id', 'userName', 'company__profilePhoto', 'company__managerFullName'
                )

            users = filter_users()
            pros = filter_professionals()

            result = [
                {
                    'id': u['id'],
                    'name': f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
                    'type': 'user',
                    'userName': u['username'],
                    'profile_image': safe_url(u.get('profileImage')) if not PrivacySetting.objects.filter(user_id=u['id'], identify_visibility='private').exists() else None
                } for u in users
            ] + [
                {
                    'id': p['id'],
                    'name': p['company__managerFullName'],
                    'type': 'professional',
                    'userName': p['userName'],
                    'profile_image': safe_url(p.get('company__profilePhoto'))
                } for p in pros
            ]

            return Response({
                'statusCode': 200,
                'status': True,
                'message': 'Mentionable entities retrieved successfully.',
                'totalResults': len(result),
                'mentionable': result
            })

        except Exception as e:
            return Response({
                'statusCode': 500,
                'status': False,
                'message': f'An error occurred: {str(e)}'
            }, status=500)

