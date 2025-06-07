import calendar
from datetime import date, datetime, timedelta

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import *
from ProfessionalUser.serializers import *
from ProfessionalUser.signals import *
from UserApp.serializers import *


class CruiseRoomAvailabilityView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            total_adults = int(request.query_params.get('adults', 0))
            total_children = int(request.query_params.get('children', 0))
            room_quantity = int(request.query_params.get('room_quantity', 1))
        except ValueError:
            return Response({"error": "Invalid input parameters."}, status=status.HTTP_200_OK)

        if total_adults == 0 and total_children == 0:
            return Response({"error": "Adults or children must be specified."}, status=400)

        rooms = CruiseRoom.objects.all()
        response_data = []

        for room in rooms:
            if room.roomQuantity >= room_quantity:
                total_adult_capacity = room.adults * room_quantity

                is_available = (
                    total_adult_capacity >= total_adults 
                )
            else:
                is_available = False

            response_data.append({
                "room_id": room.room_id,
                "roomType": room.roomType,
                "roomPrice": float(room.roomPrice),
                "available_quantity": room.roomQuantity,
                "adults_capacity": room.adults,
                "is_available": is_available
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Data fetched successfully",
            "data": response_data
        }, status=status.HTTP_200_OK)



class CruiseRoomBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            room_id = data.get('room_id')
            room_quantity = int(data.get('room_quantity'))
            adults = int(data.get('adults'))
            pets = int(data.get('pets', 0))
        except (ValueError, TypeError):
            return Response({
                "status_code": 400,
                "status": False,
                "message": "Invalid input."
            }, status=status.HTTP_200_OK)

        try:
            room = CruiseRoom.objects.get(room_id=room_id)
        except CruiseRoom.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Room not found."
            }, status=status.HTTP_200_OK)

        if room.roomQuantity < room_quantity:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Not enough room quantity available."
            }, status=status.HTTP_200_OK)

        total_adult_capacity = room.adults * room_quantity
        if total_adult_capacity < adults:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Requested group exceeds room capacity."
            }, status=status.HTTP_200_OK)

        total_price = room.roomPrice * room_quantity

        room.roomQuantity -= room_quantity
        room.save()

        booking = RoomBooking.objects.create(
            user=request.user,
            product=room.product,
            company=room.product.company,
            room=room,
            room_quantity=room_quantity,
            adults=adults,
            pets=pets,
            total_price=total_price,
            is_paid=False,
            # booking_status='pending',
            expires_at=None
        )
        professional_user = ProfessionalUser.objects.filter(company=room.product.company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="cruise room booking",
                    message=f"{request.user.username} booked '{room.product.productname}'",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{room.product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")

    
        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Booking confirmed successfully.",
            "order_id": booking.booking_id
        }, status=status.HTTP_200_OK)


def delete_expired_unpaid_bookings():
    now = timezone.now()
    expired_bookings = RoomBooking.objects.filter(
        is_paid=False,
        booking_status='pending',
        expires_at__lt=now
    )

    for booking in expired_bookings:
        booking.room.roomQuantity += booking.room_quantity
        booking.room.save()
        booking.delete()






class RoomAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        room_id = request.GET.get('room_id')

        if not room_id:
            return Response(
                {"status": False, "statusCode": 400, "message": "room_id is required."},
                status=status.HTTP_200_OK
            )

        try:
            room = Product.objects.get(id=room_id)
        except Product.DoesNotExist:
            return Response(
                {"status": False, "statusCode": 404, "message": "Room not found."},
                status=status.HTTP_200_OK
            )

        today = date.today()
        start_date = today.replace(day=1)
        end_month = (start_date.month + 4 - 1) % 12 + 1
        end_year = start_date.year + (start_date.month + 4 - 1) // 12
        last_day = calendar.monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, last_day)

        bookings = RoomBooking.objects.filter(
            product=room,
            checkin_date__lte=end_date,
            checkout_date__gte=start_date
        )

        total_rooms = int(room.quantity or 0) 
        availability = []

        current_day = start_date
        while current_day <= end_date:
            booked_qty = sum(
                int(booking.room_quantity or 0)
                for booking in bookings
                if booking.checkin_date.date() <= current_day < booking.checkout_date.date()
            )

            available_rooms = max(total_rooms - booked_qty, 0)
            is_available = booked_qty < total_rooms

            if current_day < today:
                is_available = False
                available_rooms = 0

            availability.append({
                "date": current_day.isoformat(),
                "available": is_available,
                "booked_quantity": booked_qty,
                "available_rooms": available_rooms,
                "total_rooms": total_rooms
            })

            current_day += timedelta(days=1)

        return Response(
            {
                "status": True,
                "statusCode": 200,
                "availability": availability
            },
            status=status.HTTP_200_OK
        )


class BookRoomAPIView(APIView):
    def post(self, request):
        try:
            user = request.user
            product_id = request.data.get('product_id')
            room_quantity = int(request.data.get('room_quantity', 1))
            adults = int(request.data.get('adults', 1))
            pets = int(request.data.get('pets', 0))
            checkin_date = request.data.get('checkin_date')
            checkout_date = request.data.get('checkout_date')

            if not all([product_id, checkin_date, checkout_date]):
                return Response({"message": "Missing required fields"}, status=200)
            checkin = datetime.datetime.strptime(checkin_date, "%Y-%m-%d").date()
            checkout = datetime.datetime.strptime(checkout_date, "%Y-%m-%d").date()

            if checkout <= checkin:
                return Response({"status": False, "statusCode": 404,"message": "Checkout date must be after check-in date."}, status=200)

            with transaction.atomic():
                self.revert_expired_bookings()
                self.cleanup_expired_pending_bookings()

                product = Product.objects.select_for_update().get(id=product_id)
                if pets > 0 and not product.petAllowed:
                    return Response({"status": False, "statusCode": 404,"message": "Pets not allowed for this room."}, status=200)
                for day in self.date_range(checkin, checkout):
                    total_booked = RoomBooking.objects.filter(
                        product_id=product.id,
                        booking_status__in=['confirmed', 'pending'],
                        checkin_date__lt=day + timedelta(days=1),
                        checkout_date__gt=day
                    ).aggregate(total=models.Sum('room_quantity'))['total'] or 0

                    available = product.quantity - total_booked
                    if available < room_quantity:
                        return Response({
                            "status": False, "statusCode": 404,"message": f"Insufficient room availability on {day}. Only {available} rooms available."
                        }, status=200)
                price = product.promotionalPrice or product.basePrice or product.priceOnsite or 0
                total_price = price * room_quantity
                booking = RoomBooking.objects.create(
                    user=user,
                    product=product,
                    company=product.company,
                    room_quantity=room_quantity,
                    adults=adults,
                    pets=pets,
                    total_price=total_price,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    is_paid=False,
                    booking_status='pending',
                )
                professional_user = ProfessionalUser.objects.filter(company=product.company).first()
                if professional_user:
                    try:
                        Notification.objects.create(
                            professional_user=professional_user,
                            sender=request.user,
                            title="hotel booking",
                            message=f"{request.user.username} booked '{product.productname}'",
                            notification_type="booking"
                        )
                        push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                        success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                        if not success:
                            print("Push failed or no player IDs found.")
                    except Exception as e:
                        print(f"Notification error: {e}")
                
            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Room booked successfully",
                "order_id": booking.booking_id
            }, status=200)

        except Product.DoesNotExist:
            return Response({"message": "Product not found."}, status=404)
        except Exception as e:
            return Response({"message": str(e)}, status=500)

    def date_range(self, start_date, end_date):
        for n in range((end_date - start_date).days):
            yield start_date + timedelta(n)

    def revert_expired_bookings(self):
        today = timezone.localdate()
        expired_bookings = RoomBooking.objects.filter(
            checkout_date__lte=today,
            booking_status='confirmed'
        )
        for booking in expired_bookings:
            booking.booking_status = 'completed'
            booking.save()

    def cleanup_expired_pending_bookings(self):
        now = timezone.now()
        expiry_time = now - timedelta(minutes=5)
        expired_pending = RoomBooking.objects.filter(
            booking_status='pending',
            booking_date__lt=expiry_time
        )
        expired_pending.delete()




class ValidateProductBookingView(APIView):
    def post(self, request):
        product_id = request.data.get('product_id')
        checkin_date = request.data.get('checkin_date')
        checkout_date = request.data.get('checkout_date')
        room_quantity = int(request.data.get('room_quantity', 0))
        members = int(request.data.get('members', 0))

        if not all([product_id, checkin_date, checkout_date, room_quantity, members]):
            return Response({ "status": False,
                "statusCode": 400, "message": "All fields are required."}, status=status.HTTP_200_OK)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({ "status": False,
                "statusCode": 400, "message": "Product not found."}, status=status.HTTP_200_OK)

        try:
            checkin = datetime.datetime.strptime(checkin_date, "%Y-%m-%d").date()
            checkout = datetime.datetime.strptime(checkout_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({ "status": False,
                "statusCode": 400, "message": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_200_OK)

        if checkin >= checkout:
            return Response({ "status": False,
                "statusCode": 400, "message": "Checkout date must be after check-in date."}, status=status.HTTP_200_OK)

        total_rooms = product.quantity or 0
        for single_day in (checkin + timedelta(days=n) for n in range((checkout - checkin).days)):
            total_booked = RoomBooking.objects.filter(
                product=product,
                checkin_date__lte=single_day,
                checkout_date__gt=single_day
            ).aggregate(total=models.Sum('room_quantity'))['total'] or 0

            available = total_rooms - total_booked
            if available < room_quantity:
                return Response({
                     "status": False,
                "statusCode": 400,
                    "message": f"Only {available} rooms are available on {single_day}, but {room_quantity} were requested.",
                    "debug": {
                        "product_quantity": total_rooms,
                        "total_booked_on_date": total_booked,
                        "requested_room_quantity": room_quantity,
                        "date_checked": str(single_day)
                    }
                }, status=status.HTTP_200_OK)
        max_capacity = (product.noofMembers or 0) * room_quantity
        if members > max_capacity:
            return Response({
                "status": False,
                "statusCode": 400,
                "message": f"Maximum allowed members for {room_quantity} rooms is {max_capacity}, but you provided {members}."
            }, status=status.HTTP_200_OK)

        return Response({
             "status": True,
                "statusCode": 200,
            "message": "Rooms are available and member count is within allowed limit."
        }, status=status.HTTP_200_OK)
    



class GetUnavailableDatesView(APIView):
    def post(self, request):
        product_id = request.data.get('product_id')

        if not product_id:
            return Response({"status": False,"statusCode": 400, "message": "Product ID is required."}, status=status.HTTP_200_OK)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"status": False,"statusCode": 400,"message": "Product not found."}, status=status.HTTP_200_OK)

        total_rooms = product.quantity or 0
        today = date.today()
        future_days = 90  # Customize this as needed
        end_date = today + timedelta(days=future_days)

        unavailable_dates = []

        for single_day in (today + timedelta(days=n) for n in range((end_date - today).days)):
            total_booked = RoomBooking.objects.filter(
                product=product,
                checkin_date__lte=single_day,
                checkout_date__gt=single_day
            ).aggregate(total=Sum('room_quantity'))['total'] or 0

            if total_booked >= total_rooms:
                unavailable_dates.append(str(single_day))  # Format as string for JSON response

        return Response({
            "status": True,
            "statusCode": 200,
            "product_id": product_id,
            "unavailable_dates": unavailable_dates,
            "message": f"Unavailable dates for the next {future_days} days."
        }, status=status.HTTP_200_OK)
    





class MusicBookingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user

        full_name = data.get('full_name')
        email = data.get('email')
        phone = data.get('phone')
        booking_date = data.get('booking_date')
        booking_time = data.get('booking_time')
        end_date = data.get('end_date')
        number_of_people = data.get('number_of_people', 0)
        tickets_data = data.get('tickets', [])

        if not tickets_data:
            return Response({'statusCode': 400, 'status': False, 'message': 'No tickets provided.'}, status=status.HTTP_200_OK)

        # Remove unpaid bookings older than 5 mins
        time_limit = timezone.now() - timedelta(minutes=5)
        eventBooking.objects.filter(user=user, is_paid=False, created_at__lt=time_limit).delete()

        ticket_items = []
        total_price = 0
        company = None
        product = None

        for item in tickets_data:
            ticket_type = item.get('ticket_type')
            ticket_id = item.get('ticket_id')
            quantity = item.get('quantity', 0)

            if ticket_type in ['concert', 'music_festivals']:
                ticket_model = TicketsConcert
            elif ticket_type == "nightclubs":
                ticket_model = NightClubTicket
            else:
                return Response({'statusCode': 400, 'status': False, 'message': 'Invalid ticket type.'}, status=status.HTTP_200_OK)

            try:
                ticket = ticket_model.objects.get(id=ticket_id)
                
            except ticket_model.DoesNotExist:
                return Response({'statusCode': 404, 'status': False, 'message': f'{ticket_type} ticket with ID {ticket_id} not found.'}, status=status.HTTP_200_OK)

            # Check available quantity
            ticket_ct = ContentType.objects.get_for_model(ticket)
            already_booked = BookingTicketItem.objects.filter(
                content_type=ticket_ct,
                object_id=ticket.id,
                booking__booking_date=booking_date,
                booking__is_paid=True,
                booking__status='confirmed'
            ).aggregate(total=Sum('quantity'))['total'] or 0

            available_quantity = ticket.quantity - already_booked
            if quantity > available_quantity:
                ticket_name = ticket.name if ticket_type in ['concert', 'music_festivals'] else getattr(ticket, 'tableName', 'Unknown')
                return Response({
                    'statusCode': 400,
                    'status': False,
                    'message': f'Only {available_quantity} tickets available for {ticket_name} on {booking_date}.'
                }, status=status.HTTP_200_OK)

            # Setup company & product
            if not product:
                product = ticket.product
                if not product:
                    return Response({'statusCode': 400, 'status': False, 'message': 'Ticket missing associated product.'}, status=status.HTTP_200_OK)
                company = product.company
                vat_rate = product.vatRate or 0

            base_price = ticket.price * quantity
            vat = (base_price * vat_rate) / 100
            total_price += base_price + vat
            if ticket_type in ['concert', 'music_festivals']:
                ticket_name = getattr(ticket, 'name', 'Unknown Ticket')
            else:
                ticket_name = getattr(ticket, 'tableName', 'Unknown Ticket')
            ticket_items.append({
                'model': ticket_model,
                'instance': ticket,
                'ticket_type': ticket_type,
                'ticket_id': ticket.id,
                'quantity': quantity,
                'ticket_name': ticket_name,
            })

        # Create main booking
        booking = eventBooking.objects.create(
            user=user,
            company=company,
            ticket_id=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            booking_time=booking_time,
            end_date=end_date,
            ticket_type=[{"ticket_id": t['ticket_id'], "ticket_type": t['ticket_type'], "quantity": t['quantity'],"ticket_name":t["ticket_name"]} for t in ticket_items],
            number_of_people=number_of_people,
            price=total_price,
            is_paid=False,
            # status='pending'
        )

        # Create booking ticket items
        for t in ticket_items:
            BookingTicketItem.objects.create(
                booking=booking,
                ticket=t['instance'],
                quantity=t['quantity']

            )
        
        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Booking created successfully.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)



class EventBookingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user

        tickets_data = data.get('tickets', [])
        full_name = data.get('full_name')
        email = data.get('email')
        phone = data.get('phone')
        booking_date = data.get('booking_date')
        booking_time = data.get('booking_time')
        end_date = data.get('end_date')
        price =data.get('total_price')
        time_limit = timezone.now() - timedelta(minutes=5)
        experienceBooking.objects.filter(user=user, is_paid=False, created_at__lt=time_limit).delete()

       
        total_adult = 0
        total_children = 0
        total_people = 0
        subtotal = 0    
        ticket_summary = []

        first_ticket = None  

        for ticket_entry in tickets_data:
            ticket_id = ticket_entry.get('ticket_id')
            adult = int(ticket_entry.get('adult', 0))
            children = int(ticket_entry.get('children', 0))

            try:
                ticket = TicketsAmusementPark.objects.get(id=ticket_id)
            except TicketsAmusementPark.DoesNotExist:
                return Response({'statusCode': 400, 'status': False, 'message': f'Invalid ticket ID: {ticket_id}'}, status=status.HTTP_200_OK)

            if not first_ticket:
                first_ticket = ticket

            adult_price = ticket.adultPrice or 0
            child_price = ticket.childPrice or 0
            ticket_total = (adult * adult_price) + (children * child_price)

            subtotal += ticket_total
            total_adult += adult
            total_children += children
            total_people += (adult + children)

            ticket_summary.append({
                'ticket_id': ticket.id,
                'name': ticket.name,
                'adult': adult,
                'children': children,
                'adult_price': adult_price,
                'child_price': child_price,
                'total': ticket_total
            })
        product = first_ticket.product if first_ticket else None
        company = product.company if product else None
        vat_rate = product.vatRate or 0  # get VAT % from product

        vat_amount = (subtotal * vat_rate) / 100
        total_price = subtotal + vat_amount

        booking = experienceBooking.objects.create(
            user=user,
            company=company,
            ticket_id=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            end_date=end_date,
            booking_time=booking_time,
            number_of_people=total_people,
            adult=total_adult,
            children=total_children,
            price=total_price,
            ticket_type=ticket_summary,  
            is_paid=False, 
            # status="pending"
        )
        professional_user = ProfessionalUser.objects.filter(company=company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="event booking",
                    message=f"{request.user.username} booked '{product.productname}' for {booking_date} at {booking_time}.",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")
        

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Booking created successfully.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)
    


class eventandworkshopBookingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user

        full_name = data.get('full_name')
        email = data.get('email')
        phone = data.get('phone')
        booking_date = data.get('booking_date')
        booking_time = data.get('booking_time')
        number_of_people = data.get('number_of_people', 0)
        end_date = data.get('end_date')
        tickets_data = data.get('tickets', [])

        if not tickets_data:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'No tickets provided.'
            }, status=status.HTTP_200_OK)

        total_selected_quantity = sum(ticket.get('quantity', 0) for ticket in tickets_data)
        if total_selected_quantity > 5:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'You cannot book more than 5 tickets in total.'
            }, status=status.HTTP_200_OK)
        time_limit = timezone.now() - timedelta(minutes=5)
        experienceBooking.objects.filter(
            user=user,
            is_paid=False,
            created_at__lt=time_limit
        ).delete()

        company = None
        product = None
        subtotal = 0  
        ticket_type_list = []

        for entry in tickets_data:
            ticket_id = entry.get('ticket_id')
            quantity = entry.get('quantity', 0)
            ticket_name = None

            try:
                ticket = TicketsConcert.objects.get(id=ticket_id)
                print("-------------------------",ticket)
                ticket_name = ticket.name
            except TicketsConcert.DoesNotExist:
                return Response({
                    'statusCode': 400,
                    'status': False,
                    'message': f'Ticket ID {ticket_id} not found.'
                }, status=status.HTTP_200_OK)

            if not company:
                product = ticket.product
                print("---------------",product)
                company = product.company if product else None
            booked_quantity = BookingTicketItem.objects.filter(
                booking__booking_date=booking_date,
                booking__is_paid=True,
                booking__status='confirmed'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            print("-----------",booked_quantity)

            available_quantity = ticket.quantity - booked_quantity
            if quantity > available_quantity:
                return Response({
                    'statusCode': 400,
                    'status': False,
                    'message': f'Only {available_quantity} tickets available for {ticket_name} on {booking_date}.'
                }, status=status.HTTP_200_OK)
            ticket_type_list.append({
                "name": ticket_name,
                "total": quantity,
            
            })
            print("----------",ticket_name)
            print("---------------",quantity)
            subtotal += ticket.price * quantity
            print("0-----------------",subtotal)
            vat_rate = product.vatRate or 0  
            vat_amount = subtotal * (vat_rate / 100)
            print("Ticket price:", ticket.price, "Quantity:", quantity)

            total_price = subtotal + vat_amount
            print("------------------",total_price)
            


        booking = experienceBooking.objects.create(
            user=user,
            company=company,
            ticket_id=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            booking_time=booking_time,
            end_date=end_date,
            price=total_price,
            number_of_people=number_of_people,
            quanity=total_selected_quantity,
            ticket_type=ticket_type_list,
            is_paid=False,
            # status='pending'
        )
        professional_user = ProfessionalUser.objects.filter(company=company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="event and workshop booking",
                    message=f"{request.user.username} booked '{product.productname}' for {booking_date} at {booking_time}.",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Booking created successfully.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)
    


class BookexperiencecreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        product_id = data.get('product_id')
        date_str = data.get('booking_date', '') 
        slot_str = data.get('slot')              
        full_name = data.get('full_name')

        email = data.get('email', '')
        phone = data.get('phone', '')
        number_of_people = data.get('number_of_people') or 0

        if not all([product_id, date_str, slot_str, full_name]):
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Missing required fields.'
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
            company = product.company 
            booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            slot = datetime.datetime.strptime(slot_str.strip().upper(), '%I:%M %p').time()
        except Exception as e:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': f"Invalid input: {str(e)}"
            }, status=status.HTTP_200_OK)
        exists = slotBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            slot=slot,
            status__in=['confirmed', 'pending'],
            is_paid=True
        ).exclude(user=request.user).exists()

        if exists:
            return Response({
                'statusCode': 409,
                'status': False,
                'message': 'Slot already booked.'
            }, status=status.HTTP_200_OK)
        
        base_price = product.promotionalPrice or 0
        vat_rate = product.vatRate or 0
        vat_amount = base_price * (vat_rate / 100)
        final_price = base_price + vat_amount
        booking = slotBooking.objects.create(
            user=request.user,
            company=company,
            Product=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            slot=slot,
            booking_time=slot,
            number_of_people=number_of_people,
            price=final_price,
            is_paid=False,
            # status='pending'
        )
        professional_user = ProfessionalUser.objects.filter(company=company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="experience booking",
                    message=f"{request.user.username} booked '{product.productname}' for {booking_date} at {slot}.",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Slot booked successfully. Please complete payment.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)
    





class AestheticscreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        product_id = data.get('product_id')
        date_str = data.get('booking_date', '')  # Format: YYYY-MM-DD
        slot_str = data.get('slot')              # Format: HH:MM
        full_name = data.get('full_name')
        email = data.get('email', '')
        phone = data.get('phone', '')
        number_of_people = data.get('number_of_people') or 0
        if not all([product_id, date_str, slot_str, full_name]):
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Missing required fields.'
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
            company = product.company 
            booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            slot = datetime.datetime.strptime(slot_str.strip().upper(), '%I:%M %p').time()
        except Exception as e:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': f"Invalid input: {str(e)}"
            }, status=status.HTTP_200_OK)
        exists = aestheticsBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            slot=slot,
            status__in=['confirmed', 'pending'],
            is_paid=True
        ).exclude(user=request.user).exists()

        if exists:
            return Response({
                'statusCode': 409,
                'status': False,
                'message': 'Slot already booked.'
            }, status=status.HTTP_200_OK)
        base_price = product.promotionalPrice or 0
        vat_rate = product.vatRate or 0

        subtotal = base_price * number_of_people
        vat_amount = (base_price * (vat_rate / 100)) * number_of_people
        final_price = subtotal + vat_amount
        booking = aestheticsBooking.objects.create(
            user=request.user,
            company=company,
            Product=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            slot=slot,
            booking_time=slot,
            number_of_people=number_of_people,
            price=final_price,
            is_paid=False,
        )
        professional_user = ProfessionalUser.objects.filter(company=company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="Aesthetics",
                    message=f"{request.user.username} booked '{product.productname}' for {booking_date} at {slot}.",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")


        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Slot booked successfully. Please complete payment.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)
    


class RelaxationcreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        product_id = data.get('product_id')
        date_str = data.get('booking_date', '')  # Format: YYYY-MM-DD
        slot_str = data.get('slot')              # Format: HH:MM
        full_name = data.get('full_name')
        email = data.get('email', '')
        phone = data.get('phone', '')
        number_of_people = data.get('number_of_people') or 0
        if not all([product_id, date_str, slot_str, full_name]):
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Missing required fields.'
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
            company = product.company 
            booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            slot = datetime.datetime.strptime(slot_str.strip().upper(), '%I:%M %p').time()
        except Exception as e:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': f"Invalid input: {str(e)}"
            }, status=status.HTTP_200_OK)
        exists = relaxationBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            slot=slot,
            status__in=['confirmed', 'pending'],
            is_paid=True
        ).exists()

        if exists:
            return Response({
                'statusCode': 409,
                'status': False,
                'message': 'Slot already booked.'
            }, status=status.HTTP_200_OK)
        base_price = product.promotionalPrice or 0
        vat_rate = product.vatRate or 0

        subtotal = base_price * number_of_people
        vat_amount = (base_price * (vat_rate / 100)) * number_of_people
        final_price = subtotal + vat_amount
        booking = relaxationBooking.objects.create(
            user=request.user,
            company=company,
            Product=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            slot=slot,
            booking_time=slot,
            number_of_people=number_of_people,
            price=final_price,
            is_paid=False,
        )
        professional_user = ProfessionalUser.objects.filter(company=company).first()
        if professional_user:
            try:
                Notification.objects.create(
                    professional_user=professional_user,
                    sender=request.user,
                    title="Relaxation",
                    message=f"{request.user.username} booked '{product.productname}' for {booking_date} at {slot}.",
                    notification_type="booking"
                )
                push_msg = f"New booking for '{product.productname}' by {request.user.username}."
                success = get_player_ids_by_professional_id(pro_user_id=professional_user.id, content=push_msg)
                if not success:
                    print("Push failed or no player IDs found.")
            except Exception as e:
                print(f"Notification error: {e}")


        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Slot booked successfully. Please complete payment.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)
    


class ArtandculturecreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        product_id = data.get('product_id')
        date_str = data.get('booking_date', '')  
        slot_str = data.get('slot')             
        full_name = data.get('full_name')
        email = data.get('email', '')
        phone = data.get('phone', '')
        number_of_people = int(data.get('number_of_people') or 0)

        # Validate required fields
        if not all([product_id, date_str, slot_str, full_name]):
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Missing required fields.'
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
            company = product.company 
            booking_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            slot = datetime.datetime.strptime(slot_str.strip().upper(), '%I:%M %p').time()
        except Exception as e:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': f"Invalid input: {str(e)}"
            }, status=status.HTTP_200_OK)
        exists = artandcultureBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            slot=slot,
            status__in=['confirmed', 'pending'],
            is_paid=True
        ).exists()

        if exists:
            return Response({
                'statusCode': 409,
                'status': False,
                'message': 'Slot already booked.'
            }, status=status.HTTP_200_OK)
        base_price = product.promotionalPrice or 0
        vat_rate = product.vatRate or 0 

        subtotal = base_price * number_of_people
        vat_amount = (base_price * (vat_rate / 100)) * number_of_people
        final_price = subtotal + vat_amount
        booking = artandcultureBooking.objects.create(
            user=request.user,
            company=company,
            Product=product,
            full_name=full_name,
            email=email,
            phone=phone,
            booking_date=booking_date,
            slot=slot,
            booking_time=slot,
            number_of_people=number_of_people,
            price=final_price,
            is_paid=False,
         
        )
        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Slot booked successfully. Please complete payment.',
            'order_id': booking.booking_id
        }, status=status.HTTP_200_OK)