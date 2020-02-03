# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
# Construct the header to reorder sequence
import struct
from threading import Timer
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
        self.data = b''
        self.seqnum = 0  # sending seq num
        self.recvnum = 1  # receiver's current receiving number in order
        self.buffer = {}  # receiving buffer
        self.ack = []    # all the ACKs we've received
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.executor.submit(self.listener)
        self.TIMER_THREAD = {}

        print("Initial finished.")

    def listener(self) -> None:
        while True:

            ss, addr = self.socket.recvfrom()
            if len(ss) <= 2:# if receive ACK, STOP corresponding TIMER

                cmd = "!H"
                this_ack, = struct.unpack(cmd, ss)
                t = self.TIMER_THREAD.get(this_ack)
                t.cancel()  # STOP the timer, and REMOVE it from dict
                self.TIMER_THREAD.pop(this_ack)
                self.ack.append(this_ack)
                print("==I got ACK: ==", this_ack)


            else:           # if receive DATA, put into buffer
                cmd = "!H" + str(len(ss) - 2) + "s"
                header, data = struct.unpack(cmd, ss)
                #print("Got header is %d" % header)

                if header < self.recvnum:
                    ack = struct.pack("!H", header)
                    self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                else:
                    self.buffer.update({header: data})

                    ack = struct.pack("!H", header)
                    self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                    #print("--Sent ACK:", header)


    def retransmission(self,ss):

        # deparse the ss to get the header
        cmd = "!H" + str(len(ss)-2) + "s"
        header, dt = struct.unpack(cmd, ss)
        print("ack[]: ", self.ack)
        if header not in self.ack:
            # resend ss after exceeding time
            self.socket.sendto(ss, (self.dst_ip, self.dst_port))

            t1 = self.TIMER_THREAD.get(header)
            t1.cancel()
            self.TIMER_THREAD.pop(header)
            print("!!Resend!!:", header,"; ",dt)
            # recreate a Timer for this send
            t2 = Timer(0.25, self.retransmission, (ss,))  # self.seqnum,
            self.TIMER_THREAD.update({header: t2})
            t2.start()
        else:
            self.TIMER_THREAD.pop(header)


        # if ss < self.ack:
        #     cmd = "!H" + str(len(self.data)) + "s"
        #     ss = struct.pack(cmd, ss, self.data)
        #     self.socket.sendto(ss, (self.dst_ip, self.dst_port))
        #     print("retransmit {%s}" % ss.decode())


    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!

        raw_data = data_bytes
        self.data = raw_data
        while True:

            if len(raw_data) > 1470:
                packet_data_bytes = raw_data[0:1470]  # !python note: range needs to cover the higher index
                raw_data = raw_data[1470:]
                self.seqnum += 1

                ss = struct.pack("!H1470s", self.seqnum, packet_data_bytes)

                self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                t = Timer(0.25, self.retransmission, (ss,))
                self.TIMER_THREAD.update({self.seqnum: t})
                t.start()

            else:

                if len(raw_data) != 0:
                    self.seqnum += 1

                    cmd = "!H" + str(len(raw_data)) + "s"
                    ss = struct.pack(cmd, self.seqnum, raw_data) #???? seqnum

                    self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                    t = Timer(0.25, self.retransmission, (ss,)) #self.seqnum,
                    self.TIMER_THREAD.update({self.seqnum: t})
                    t.start()

                break


    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        rs = ''

        while True:
            if self.buffer == {}:
                continue

            m = max(self.buffer.keys())
            for i in range(self.recvnum, m + 1):
                #print("recv()",self.recvnum,", ",self.buffer.keys())
                if self.recvnum in self.buffer.keys():
                    rs = rs + self.buffer.pop(self.recvnum).decode()
                    #print("Rs+=pop: ", rs, " recv#: ", self.recvnum)
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
