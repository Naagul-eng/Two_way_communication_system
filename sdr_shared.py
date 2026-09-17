import queue

# Thread-safe IPC message queues between GUI and GNU Radio worker threads
tx_queue = queue.Queue()
rx_queue = queue.Queue()