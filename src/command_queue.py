from queue import Queue
import zone
import datetime
import json

class CommandQueue:
    def __init__(self):
        self.queue = Queue()

    def enqueue(self, command : zone.ZoneCommand):
        self.queue.put(command)

    def dequeue(self):
        return self.queue.get()

    def peek(self):
        if not self.is_empty():
            return self.queue.queue[0]

    def is_empty(self):
        return self.queue.empty()
    
    def empty_queue(self):
        while not self.queue.empty():
            self.queue.get()
    
    def to_list(self):
        return list(self.queue.queue)
    
    def total_command_time(self) -> datetime.timedelta:
        total_time = datetime.timedelta()
        for command in self.to_list():
            total_time += command.run_time
        return total_time