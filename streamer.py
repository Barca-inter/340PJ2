# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
# Construct the header to reorder sequence
import struct



from concurrent.futures import ThreadPoolExecutor
import threading

import time
from concurrent.futures import ThreadPoolExecutor


class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        self.seqnum = 0  # sending seq num
        self.recvnum = 0  # receiver's current receiving number
        self.buffer = {}  # receiving buffer
        self.ack = 0
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.executor.submit(self.listener)
        print("Start bg recv..")

    def listener(self) -> None:
        while True:
            # print('1 listener')
            ss, addr = self.socket.recvfrom()
            if len(ss) <= 2:
                cmd = "!H"
                self.ack, = struct.unpack(cmd, ss)
            else:
                cmd = "!H" + str(len(ss) - 2) + "s"
                header, data = struct.unpack(cmd, ss)
                if header < self.recvnum:
                    continue
                self.buffer.update({header: data})
            # print(ss)

    def retr(self,hd,data):
        if hd >= self.ack:
            print("retransmit {%s}" % data.decode())


    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!

        header = self.seqnum
        raw_data = data_bytes


        while True:

            if len(raw_data) > 1470:
                packet_data_bytes = raw_data[0:1470]  # !python note: range needs to cover the higher index
                raw_data = raw_data[1470:]
                ss = struct.pack("!H1470s", header, packet_data_bytes)

                header += 1
                self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                threading.Timer(0.25, self.retr, header,raw_data)
            else:

                if len(raw_data) != 0:
                    cmd = "!H" + str(len(raw_data)) + "s"
                    ss = struct.pack(cmd, header, raw_data)
                    header += 1
                    self.socket.sendto(ss, (self.dst_ip, self.dst_port))

                break
        self.seqnum = header

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        rs = ''

        while True:
            if not self.buffer.keys():
                continue

            m = max(self.buffer.keys())
            for i in range(self.recvnum, m + 1):
                if self.recvnum in self.buffer.keys():
                    rs = rs + self.buffer.pop(self.recvnum).decode()
                    self.recvnum += 1

            if rs == '':
                continue

            break

        return rs.encode()

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.

        # self.pool.shutdown()
        pass

