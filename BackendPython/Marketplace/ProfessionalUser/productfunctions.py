import json

from rest_framework import status
from rest_framework.response import Response

from ProfessionalUser.models import *


def create_tickets_concert(tickets_data_raw, product):
    try:
        
        if tickets_data_raw is None:
            return []
        
        if isinstance(tickets_data_raw, str):
            tickets_data = json.loads(tickets_data_raw)
        elif isinstance(tickets_data_raw, list):
            tickets_data = tickets_data_raw
        else:
            raise ValueError("ticketsConcert must be a list or JSON string")

        created_tickets = []
        for ticket in tickets_data:
            concert_ticket = TicketsConcert.objects.create(
                product=product,
                name=ticket.get("name", ""),
                price=ticket.get("price", 0),
                members =ticket.get("members", 0),
                quantity=ticket.get("quantity", 0),
                description=ticket.get("description", "")
            )
            created_tickets.append({
                "id": concert_ticket.id,
                "name": concert_ticket.name,
                "price": concert_ticket.price,
                "members": concert_ticket.members,
                "quantity": concert_ticket.quantity,
                "description": concert_ticket.description,
            })
     
        return created_tickets

    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid ticketsConcert format: {str(e)}")


def create_tickets_nightclub(nightClub_data_raw, product):
    try:

        if nightClub_data_raw is None:
            return []
        if isinstance(nightClub_data_raw, str):
            nightclub_tickets_data = json.loads(nightClub_data_raw)
        elif isinstance(nightClub_data_raw, list):
            nightclub_tickets_data = nightClub_data_raw
        else:
            raise ValueError("nightClub_data_raw must be a list or JSON string")

        created_tickets_nightclub = []

        for ticket in nightclub_tickets_data:

            concert_ticket = NightClubTicket.objects.create(
                product=product,
                tableName=ticket.get("tableName", ""),
                price=ticket.get("price", 0),
                members=ticket.get("members", 0),
                quantity=ticket.get("quantity", 0),
                description=ticket.get("description", "")
            )

            created_tickets_nightclub.append({
                "id": concert_ticket.id,
                "tableName": concert_ticket.tableName,
                "price": concert_ticket.price,
                "members": concert_ticket.members,
                "quantity": concert_ticket.quantity,
                "description": concert_ticket.description,
            })

        return created_tickets_nightclub

    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid nightClub_data_raw format: {str(e)}")


def create_tickets_amusements(amusements_data_raw, product):
    try:

        if amusements_data_raw is None:
            return []
        if isinstance(amusements_data_raw, str):
            amusements_tickets_data = json.loads(amusements_data_raw)
           
        elif isinstance(amusements_data_raw, list):
            amusements_tickets_data = amusements_data_raw
        else:
            raise ValueError("nightClub_data_raw must be a list or JSON string")

        created_tickets_amusements = []

        for ticket in amusements_tickets_data:
        

            concert_ticket = TicketsAmusementPark.objects.create(
                product=product,
                name=ticket.get("name", ""),
                adultPrice=ticket.get("adultPrice", 0),
                childPrice = ticket.get("childPrice", 0),
                description=ticket.get("description", "")
            )

            created_tickets_amusements.append({
                "id": concert_ticket.id,
                "name": concert_ticket.name,
                "adultPrice": concert_ticket.adultPrice,
                "childPrice": concert_ticket.childPrice,
                "description": concert_ticket.description,
            })

        return created_tickets_amusements

    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid nightClub_data_raw format: {str(e)}")


def get_roomFacility(room_facility_raw):
    if not room_facility_raw:
        return []
    if isinstance(room_facility_raw, str):
        try:
            parsed = json.loads(room_facility_raw)
            if isinstance(parsed, list) and all(isinstance(pk, int) for pk in parsed):
                return parsed
        except json.JSONDecodeError:
            try:
                return [int(pk.strip()) for pk in room_facility_raw.split(',') if pk.strip()]
            except ValueError:
                raise ValueError("roomFacility must be a comma-separated list of integers.")

        raise ValueError("roomFacility string is invalid.")
    if isinstance(room_facility_raw, list):
        if all(isinstance(pk, int) for pk in room_facility_raw):
            return room_facility_raw
        else:
            raise ValueError("roomFacility list must contain only integers.")

    raise ValueError("roomFacility must be a list of integers or a JSON string representing a list.")

def parse_json_field(data, field_name):
    raw_value = data.get(field_name)
    if raw_value is not None:
        if isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                raise ValueError(f"{field_name} must be valid JSON string.")
        elif isinstance(raw_value, list):
            parsed = raw_value
        else:
            raise ValueError(f"{field_name} must be a JSON array string or a list.")

        if not isinstance(parsed, list):
            raise ValueError(f"{field_name} must be a list.")

        data[field_name] = parsed

def parse_list_field_and_set(data, field_name):
    
    raw_value = data.get(field_name)
    if not raw_value:
        return True, None  # skip if not present

    try:
        if isinstance(raw_value, str):
            parsed_value = json.loads(raw_value)
        elif isinstance(raw_value, list):
            parsed_value = raw_value
        else:
            parsed_value = [int(raw_value)]

        if not isinstance(parsed_value, list):
            raise ValueError(f"{field_name} must be a list")

        data.setlist(field_name, parsed_value)
        return True, None

    except (json.JSONDecodeError, ValueError) as e:
        return False, Response({
            "statusCode": 400,
            "status": False,
            "message": {field_name: [f"Invalid format for {field_name}.", str(e)]}
        }, status=status.HTTP_200_OK)

def update_tickets(request, product):
    concert_response = []
    nightclub_response = []
    amusements_response = []
    concert_data = request.data.get("concertTicket")

    if concert_data:
        if isinstance(concert_data, str):
            try:
                concert_data = json.loads(concert_data)
            except json.JSONDecodeError as e:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": f"Invalid concert_tickets data: {str(e)}"
                    },
                    status=status.HTTP_200_OK,
                )

        if not isinstance(concert_data, list):
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "concertTicket should be a list of dictionaries"
                },
                status=status.HTTP_200_OK,
            )

        for ticket_data in concert_data:
            if isinstance(ticket_data, dict):
                ticket_id = ticket_data.get("id")

                try:
                    ticket = product.ticketsconcert_set.get(id=ticket_id)

                    ticket.name = ticket_data.get("name", ticket.name)
                    ticket.description = ticket_data.get("description", ticket.description)
                    ticket.members = ticket_data.get("members", ticket.members)
                    ticket.quantity = ticket_data.get("quantity", ticket.quantity)
                    ticket.price = ticket_data.get("price", ticket.price)
                    ticket.save()

                except TicketsConcert.DoesNotExist:
                    return Response(
                        {
                            "statusCode": 404,
                            "status": False,
                            "message": f"Concert ticket with id {ticket_id} does not exist."
                        },
                        status=status.HTTP_200_OK,
                    )
            else:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Each concert ticket should be a dictionary"
                    },
                    status=status.HTTP_200_OK,
                )

    concert_response = [
        {
            "id": ticket.id,
            "name": ticket.name,
            "description": ticket.description,
            "members": ticket.members,
            "quantity": ticket.quantity,
            "price": str(ticket.price)
        }
        for ticket in product.ticketsconcert_set.all()
    ]
    club_data = request.data.get("nightClubTicket")

    if club_data:
        if isinstance(club_data, str):
            try:
                club_data = json.loads(club_data)
            except json.JSONDecodeError as e:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": f"Invalid nightclub_tickets data: {str(e)}"
                    },
                    status=status.HTTP_200_OK,
                )

        if not isinstance(club_data, list):
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "nightClubTicket should be a list of dictionaries"
                },
                status=status.HTTP_200_OK,
            )

        for ticket_data in club_data:
            if isinstance(ticket_data, dict):
                ticket_id = ticket_data.get("id")
                try:
                    ticket = product.nightclubticket_set.get(id=ticket_id)

                    ticket.tableName = ticket_data.get("tableName", ticket.tableName)
                    ticket.description = ticket_data.get("description", ticket.description)
                    ticket.members = ticket_data.get("members", ticket.members)
                    ticket.quantity = ticket_data.get("quantity", ticket.quantity)
                    ticket.price = ticket_data.get("price", ticket.price)
                    ticket.save()

                except NightClubTicket.DoesNotExist:
                    return Response(
                        {
                            "statusCode": 404,
                            "status": False,
                            "message": f"Nightclub ticket with id {ticket_id} does not exist."
                        },
                        status=status.HTTP_200_OK,
                    )
            else:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Each nightclub ticket should be a dictionary"
                    },
                    status=status.HTTP_200_OK,
                )

    nightclub_response = [
        {
            "id": ticket.id,
            "tableName": ticket.tableName,
            "description": ticket.description,
            "members": ticket.members,
            "quantity": ticket.quantity,
            "price": str(ticket.price)
        }
        for ticket in product.nightclubticket_set.all()
    ]

    park_data = request.data.get("amusementsTicket")

    if park_data:
        if isinstance(park_data, str):
            try:
                park_data = json.loads(park_data)
            except json.JSONDecodeError as e:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": f"Invalid amusements park tickets data: {str(e)}"
                    },
                    status=status.HTTP_200_OK,
                )

        if not isinstance(park_data, list):
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "amusementsTicket should be a list of dictionaries"
                },
                status=status.HTTP_200_OK,
            )

        for ticket_data in park_data:
            if isinstance(ticket_data, dict):
                ticket_id = ticket_data.get("id")
                try:
                    ticket = product.ticketsamusementpark_set.get(id=ticket_id)

                    ticket.name = ticket_data.get("name", ticket.name)
                    ticket.description = ticket_data.get("description", ticket.description)
                    ticket.adultPrice = ticket_data.get("adultPrice", ticket.adultPrice)
                    ticket.childPrice = ticket_data.get("childPrice", ticket.childPrice)
                    ticket.save()

                except TicketsAmusementPark.DoesNotExist:
                    return Response(
                        {
                            "statusCode": 404,
                            "status": False,
                            "message": f"Amusement park ticket with id {ticket_id} does not exist."
                        },
                        status=status.HTTP_200_OK,
                    )
            else:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Each amusementsTicket item should be a dictionary"
                    },
                    status=status.HTTP_200_OK,
                )
    amusements_response = [
        {
            "id": ticket.id,
            "name": ticket.name,
            "description": ticket.description,
            "adultPrice": ticket.adultPrice,
            "childPrice": ticket.childPrice,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }
        for ticket in product.ticketsamusementpark_set.all()
    ]

    
    return {
        "concert_tickets": concert_response,
        "nightclub_tickets": nightclub_response,
        "amusements_tickets": amusements_response
    }

def update_rooms(request, product):
    rooms_data = request.data.get("rooms")
    if not rooms_data:
        return [
            {
                "id": room.id,
                "roomType": room.roomType,
                "roomQuantity": room.roomQuantity,
                "roomPrice": str(room.roomPrice),
                "total_member": room.adults,
                "room_id": room.room_id,
            }
            for room in product.rooms.all()
        ]
    if isinstance(rooms_data, str):
        try:
            rooms_data = json.loads(rooms_data)
        except json.JSONDecodeError as e:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": f"Invalid rooms data: {str(e)}"
                },
                status=status.HTTP_200_OK,
            )
    if not isinstance(rooms_data, list):
        return Response(
            {
                "statusCode": 400,
                "status": False,
                "message": "Rooms should be a list of dictionaries"
            },
            status=status.HTTP_200_OK,
        )

    for room_data in rooms_data:
        if isinstance(room_data, dict):
            room_id = room_data.get("room_id")
            try:
                room = product.rooms.get(room_id=room_id)

                if "roomType" in room_data:
                    room.roomType = room_data["roomType"]
                if "roomQuantity" in room_data:
                    room.roomQuantity = room_data["roomQuantity"]
                if "roomPrice" in room_data:
                    room.roomPrice = room_data["roomPrice"]
                if "adults" in room_data:
                    room.adults = room_data["adults"]

                room.save()

            except CruiseRoom.DoesNotExist:
                return Response(
                    {
                        "statusCode": 404,
                        "status": False,
                        "message": f"Room with room_id {room_id} does not exist."
                    },
                    status=status.HTTP_200_OK,
                )
        else:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": "Each room should be a dictionary"
                },
                status=status.HTTP_200_OK,
            )
    return [
        {
            "id": room.id,
            "roomType": room.roomType,
            "roomQuantity": room.roomQuantity,
            "roomPrice": str(room.roomPrice),
            "total_member": room.adults,
            "room_id": room.room_id,
        }
        for room in product.rooms.all()
    ]
    