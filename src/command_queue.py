from queue import Queue
import src.zone as zone

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