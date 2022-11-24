#!/usr/bin/env python
from i3ipc import Connection, Con, events, Event, InputEvent, WindowEvent, InputReply
from i3ipc.events import WindowEvent
from collections import deque

import io
import typing
import subprocess

CHILD_LEAVE_CONTAINER_EVENTS = (Event.WINDOW_CLOSE, Event.WINDOW_MOVE, Event.WINDOW_FLOATING)
CHILD_NEW_LOCATION_EVENTS = (Event.WINDOW_MOVE, Event.WINDOW_NEW, Event.WINDOW_FLOATING)

NOTE_APP_ID="com.github.flxzt.rnote"

tablets: typing.Set[typing.Tuple[str, int, int]] = set()

TABLET_SIZES = {
    # Vendor ID, Product ID = Pen Width, Pen Height
    (1386, 210): (147, 91),
    (10429, 2328): (212, 135)
}


def find_note_app_container(ipc: Connection) -> typing.Optional[Con]:
    for node in walk_tree(ipc):
        if node.app_id == NOTE_APP_ID:
            return node

    return None


def walk_tree(ipc: Connection) -> typing.Iterable[Con]:
    root = ipc.get_tree().root()
    queue: typing.Deque[Con] = deque()
    queue.append(root)

    while queue:
        cur = queue.popleft()

        if cur.layout in ("stacked", "tabbed"):
            continue

        queue.extend(node for node in cur.nodes)

        yield cur


def overscan(tablet_size: typing.Tuple[int, int], window_size: typing.Tuple[int, int]):
    tablet_ratio = tablet_size[0] / tablet_size[1]

    width_from_height = int(window_size[1] * tablet_ratio)

    if width_from_height > window_size[0]:
        return width_from_height, window_size[1]
    else:
        return (window_size[0], int(window_size[0] // tablet_ratio))


def on_window(ipc: Connection, event: WindowEvent):
    container = find_note_app_container(ipc)
    if not container:
        return

    rect = container.rect

    for identifier, *ident_pair in tablets:
        ident_pair = tuple(ident_pair)
        tablet_size = TABLET_SIZES[ident_pair]
        width, height = overscan(tablet_size, (rect.width, rect.height))
        command = f"input {identifier} map_to_region {rect.x} {rect.y} {width} {height}"
        ipc.command(command)


def on_input_added(ipc: Connection, event: InputEvent):
    if event.input.type == "tablet_tool":
        add_input(event.input)


def add_input(input_device: InputReply):
    ident = input_device.identifier
    vendor = input_device.vendor
    product = input_device.product

    tablets.add((ident, vendor, product))


def on_input_removed(ipc: Connection, event: InputEvent):
    ident = event.input.identifier
    vendor = event.input.vendor
    product = event.input.product

    if event.input.type == "tablet_tool":
        try:
            tablets.remove((ident, vendor, product))
        except KeyError:
            print("Removed tablet was not registered")


def main():
    ipc = Connection()

    for input_device in ipc.get_inputs():
        if input_device.type == "tablet_tool":
            add_input(input_device)

    for event in CHILD_LEAVE_CONTAINER_EVENTS:
        ipc.on(event, on_window)

    ipc.on(Event.WINDOW, on_window)
    ipc.on(Event.INPUT_ADDED, on_input_added)
    ipc.on(Event.INPUT_REMOVED, on_input_removed)

    ipc.main()


if __name__ == "__main__":
    main()
