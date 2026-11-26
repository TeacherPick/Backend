import base64
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

PREFIX = "/api/v1/dm"
PDF = b"%PDF-1.7\n"


def open_room(client, headers, recipient_id):
    created = client.post(PREFIX + "/rooms", headers=headers, json={"recipient_id": recipient_id})
    assert created.status_code == 200, created.text
    return created.json()["room_id"]


def test_dm_realtime_read_unread_attachment_and_leave(client, user):
    teacher, sender_headers = user()
    instructor, receiver_headers = user("instructor")
    outsider, outsider_headers = user()
    room_id = open_room(client, sender_headers, instructor["id"])
    assert open_room(client, sender_headers, instructor["id"]) == room_id
    assert open_room(client, receiver_headers, teacher["id"]) == room_id
    path = f"{PREFIX}/rooms/{room_id}"
    assert client.get(path + "/messages", headers=outsider_headers).status_code == 404
    assert client.post(PREFIX + "/rooms", headers=sender_headers, json={"recipient_id": outsider["id"]}).status_code == 403
    assert client.get(PREFIX + "/rooms", headers=receiver_headers).json()["items"][0]["unread_count"] == 0
    token = receiver_headers["Authorization"].split()[1]
    with client.websocket_connect(PREFIX + "/ws", headers=sender_headers) as sender, client.websocket_connect(
        PREFIX + "/ws", subprotocols=["instructor.dm.v1", token],
    ) as receiver:
        assert sender.receive_json()["type"] == "ready"
        assert receiver.receive_json()["type"] == "ready"
        command = {"type": "message.send", "room_id": room_id, "client_id": str(uuid4()), "body": "수업 문의"}
        sender.send_json(command)
        ack = sender.receive_json()
        assert ack["type"] == "message.ack"
        message_id = ack["message"]["id"]
        assert receiver.receive_json() == {"type": "room.updated", "room_id": room_id, "latest_message_id": message_id}
        assert client.get(PREFIX + "/rooms", headers=receiver_headers).json()["items"][0]["unread_count"] == 1
        receiver.send_json({"type": "room.enter", "room_id": room_id})
        assert receiver.receive_json() == {"type": "room.entered", "room_id": room_id, "after_id": message_id}
        assert client.get(PREFIX + "/rooms", headers=receiver_headers).json()["items"][0]["unread_count"] == 0
        sender.send_json({
            **command, "client_id": str(uuid4()), "body": None,
            "attachment": {"filename": "자료.pdf", "data_base64": base64.b64encode(PDF).decode()},
        })
        attachment_event = receiver.receive_json()
        assert attachment_event["type"] == "message.created"
        attachment = attachment_event["message"]
        download = f"{path}/messages/{attachment['id']}/attachment"
        assert client.get(download, headers=receiver_headers).content == PDF
        assert client.get(download, headers=outsider_headers).status_code == 404
        history = client.get(path + "/messages", headers=receiver_headers, params={"size": 1}).json()
        assert history["items"][0]["id"] == attachment["id"]
        older = client.get(
            path + "/messages", headers=receiver_headers, params={"before_id": history["next_before_id"]},
        ).json()
        assert older["items"][0]["id"] == message_id
        receiver.send_json({"type": "room.exit"})
        assert receiver.receive_json() == {"type": "room.exited", "room_id": room_id}
        sender.send_json({**command, "client_id": str(uuid4()), "body": "추가 일정 문의"})
        assert receiver.receive_json()["type"] == "room.updated"
        assert client.get(PREFIX + "/rooms", headers=receiver_headers).json()["items"][0]["unread_count"] == 1
    assert client.delete(path, headers=receiver_headers).status_code == 204
    assert client.get(path + "/messages", headers=receiver_headers).status_code == 404
    assert client.get(PREFIX + "/rooms", headers=receiver_headers).json()["total"] == 0
    assert open_room(client, receiver_headers, teacher["id"]) == room_id
    assert client.get(path + "/messages", headers=receiver_headers).json()["items"] == []
    assert client.get(path + "/messages", headers=sender_headers).json()["items"][0]["id"] == message_id


def test_dm_websocket_access_revocation_and_idempotency(client, user, administrator):
    _, teacher = user()
    instructor, _ = user("instructor")
    _, stranger = user()
    _, admin = administrator
    room_id = open_room(client, teacher, instructor["id"])
    protocol_path = PREFIX + "/ws"
    with pytest.raises(WebSocketDisconnect) as unauthenticated:
        with client.websocket_connect(protocol_path):
            pytest.fail("Unauthenticated connection was accepted.")
    assert unauthenticated.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect(protocol_path, headers={**teacher, "Origin": "https://other.example.com"}):
            pytest.fail("Unexpected origin was accepted.")
    assert denied.value.code == 4403
    command = {"type": "message.send", "room_id": room_id, "client_id": str(uuid4()), "body": "교육 가능 일정"}
    with client.websocket_connect(protocol_path, headers=stranger) as socket:
        assert socket.receive_json()["type"] == "ready"
        socket.send_json(command)
        assert socket.receive_json()["code"] == "room_not_found"
    with client.websocket_connect(protocol_path, headers=teacher) as socket:
        assert socket.receive_json()["type"] == "ready"
        socket.send_json({"type": "message.send", "room_id": room_id, "client_id": str(uuid4())})
        assert socket.receive_json()["code"] == "invalid_command"
        socket.send_json(command)
        first = socket.receive_json()
        socket.send_json(command)
        duplicate = socket.receive_json()
        assert duplicate == first
        history = client.get(f"{PREFIX}/rooms/{room_id}/messages", headers=teacher).json()
        assert len(history["items"]) == 1
        assert client.delete(f"/api/v1/admin/accounts/{instructor['id']}", headers=admin).status_code == 204
        socket.send_json({**command, "client_id": str(uuid4())})
        assert socket.receive_json()["code"] == "recipient_unavailable"
        assert client.post("/api/v1/auth/logout", headers=teacher).status_code == 204
        with pytest.raises(WebSocketDisconnect) as revoked:
            socket.receive_json()
        assert revoked.value.code == 4401
