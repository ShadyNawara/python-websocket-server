from utils import session, client_session, server
from time import sleep

import websocket
import pytest


def test_send_close(client_session):
    """
    Ensure client stops receiving data once we send_close (socket is still open)
    """
    client, server = client_session
    assert client.received_messages == []

    server.send_message_to_all("test1")
    sleep(0.5)
    assert client.received_messages == ["test1"]

    # After CLOSE, client should not be receiving any messages
    server.clients[-1]["handler"].send_close()
    sleep(0.5)
    server.send_message_to_all("test2")
    sleep(0.5)
    assert client.received_messages == ["test1"]


def test_shutdown_gracefully(client_session):
    client, server = client_session
    assert client.ws.sock and client.ws.sock.connected
    assert server.socket.fileno() > 0

    server.shutdown_gracefully()
    sleep(0.5)

    # Ensure all parties disconnected
    assert not client.ws.sock
    assert server.socket.fileno() == -1
    assert not server.clients


def test_shutdown_abruptly(client_session):
    client, server = client_session
    assert client.ws.sock and client.ws.sock.connected
    assert server.socket.fileno() > 0

    server.shutdown_abruptly()
    sleep(0.5)

    # Ensure server socket died
    assert server.socket.fileno() == -1

    # Ensure client handler terminated
    assert server.received_messages == []
    assert client.errors == []
    client.ws.send("1st msg after server shutdown")
    sleep(0.5)

    # Note the message is received since the client handler
    # will terminate only once it has received the last message
    # and break out of the keep_alive loop. Any consecutive messages
    # will not be received though.
    assert server.received_messages == ["1st msg after server shutdown"]
    assert len(client.errors) == 1
    assert isinstance(client.errors[0], websocket._exceptions.WebSocketConnectionClosedException)

    # Try to send 2nd message
    with pytest.raises(websocket._exceptions.WebSocketConnectionClosedException):
        client.ws.send("2nd msg after server shutdown")


def test_client_closes_gracefully(session):
    client, server = session
    assert client.connected
    assert server.clients
    old_client_handler = server.clients[0]["handler"]
    client.close()
    assert not client.connected

    # Ensure server closed connection.
    # We test this by having the server trying to send
    # data to the client
    assert not server.clients
    with pytest.raises(BrokenPipeError):
        old_client_handler.connection.send(b"test")
