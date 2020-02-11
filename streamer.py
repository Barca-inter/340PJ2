# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
# Construct the header to reorder sequence
import struct
from threading import Timer
from concurrent.futures import ThreadPoolExecutor
import hashlib
import time


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
        self.ack = []  # all the ACKs we've received
        self.TIMER_THREAD = {}
        self.MD5 = {}
        self.fin = 0  # initialize the fin signal
        self.finACK = 0  # initialize the ACK of fin
        self.flag = 1
        self.secfin = 0
        self.retranHeader = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.executor.submit(self.listener)

    def listener(self) -> None:
        # print(self.flag)
        while self.flag == 1:

            ss, addr = self.socket.recvfrom()
            if addr == ("", 0):
                # print(self.flag)
                break
            if len(ss) <= 34:  # if receive ACK, STOP corresponding TIMER
                cmd = "!H32s"
                this_ack, ackchsm = struct.unpack(cmd, ss)
                print(type(this_ack))

                rcv_csm = self.getchecksum(this_ack.encode())


                print("receive ack_checksum:  " , rcv_csm)

                if rcv_csm == ackchsm.decode():
                    self.ack.append(this_ack)
                    # print("ack:", self.ack)
                    if this_ack == 0:
                        self.finACK = 1

                # print("==I got ACK: ==", this_ack)

            else:  # if receive DATA, put into buffer
                cmd = "!H32s" + str(len(ss) - 34) + "s"
                header_sq, chsm, data = struct.unpack(cmd, ss)
                print("receive data header",header_sq)
                print("receive data :",data)
                # print("Got header is %d" % header)

                # if checksum is wrong, drop the packet, resend
                databody = str(header_sq).encode() + data
                recv_chsm = self.getchecksum(databody).encode()
                # print("databody",databody)
                # print("chsm:",chsm)
                print("recv_chsm",recv_chsm)

                if recv_chsm != chsm:
                    print("recv_chsm != chsm")
                    continue
                if recv_chsm == chsm:
                    print("recv_chsm == chsm")
                    if header_sq < self.recvnum:
                        print("header<recvnum, recvnum is ", self.recvnum)
                        ack = struct.pack("!H32s", header_sq, self.getchecksum(str(header_sq).encode()).encode()) #--ack = struct.pack("!H", header_sq)

                        # self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                    else:

                        self.buffer.update({header_sq: data})
                        print("buffer.update::::", self.buffer)
                        # print("buffer update header:",header_sq)
                        ack = struct.pack("!H32s", header_sq, self.getchecksum(str(header_sq).encode()).encode()) #ack = struct.pack("!H", header_sq)
                        print("buffer:",self.buffer)
                    # print("send ack", ack)
                    self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                    # print("--Sent ACK:", header_sq)

                else:
                    # print("ERROR checksum, dropped the packet..")
                    # print("##:", header_sq)

                    continue  # ignore this packet

    def retransmission(self, ss: struct) -> None:
        # resend ss after exceeding time
        # self.socket.sendto(ss, (self.dst_ip, self.dst_port))
        # deparse the ss to get the header
        time.sleep(0.25)
        cmd = "!H32s" + str(len(ss) - 34) + "s"
        header, _, dt = struct.unpack(cmd, ss)

        if header not in self.ack:
            self.socket.sendto(ss, (self.dst_ip, self.dst_port))
            t2 = Timer(0.5, self.retransmission, (ss,))  # self.seqnum,
            if dt != str("\r\n").encode():
                self.TIMER_THREAD.update({header: t2})
            t2.start()

        else:
            if dt == str("\r\n").encode():
                if self.finACK != 1:
                    Timer(1, self.retransmission, (ss,)).start()
            if dt != str("\r\n").encode():
                self.TIMER_THREAD.pop(header)

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!

        raw_data = data_bytes
        self.data = raw_data
        while True:

            if len(raw_data) > 1438:
                packet_data_bytes = raw_data[0:1438]  # !python note: range needs to cover the higher index
                raw_data = raw_data[1438:]
                self.seqnum += 1

                # warp header+data, combine seqNum & checksum
                databody = str(self.seqnum).encode() + packet_data_bytes

                chks = self.getchecksum(databody).encode()
                # print("CHECKSUM LEN: ", len(chks))
                ss = struct.pack("!H32s1438s", self.seqnum, chks, packet_data_bytes)

                self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                t_1 = Timer(0.5, self.retransmission, (ss,))
                self.TIMER_THREAD.update({self.seqnum: t_1})
                t_1.start()
                time.sleep(0.1)

            else:

                if len(raw_data) != 0:
                    self.seqnum += 1
                    # self.retranHeader.update({self.seqnum:1})
                    cmd = "!H32s" + str(len(raw_data)) + "s"
                    databody = str(self.seqnum).encode() + raw_data
                    chks = self.getchecksum(databody).encode()
                    ss = struct.pack(cmd, self.seqnum, chks, raw_data)

                    self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                    t = Timer(0.5, self.retransmission, (ss,))
                    if raw_data != str("\r\n").encode():
                        self.TIMER_THREAD.update({self.seqnum: t})
                    t.start()
                    time.sleep(0.1)

                break

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        rs = ''

        while True:
            if self.buffer == {}:
                continue

            m = max(self.buffer.keys())
            for i in range(self.recvnum, self.recvnum + 20):
                if self.recvnum in self.buffer.keys():
                    rs = rs + self.buffer.pop(self.recvnum).decode()
                    self.recvnum += 1

            if rs == '':
                continue

            break

        return rs.encode()

    def getchecksum(self, databody):
        md5 = hashlib.md5()
        md5.update(databody)
        chks = md5.hexdigest()
        # self.MD5.update({seq:chks})
        return chks

    def SecondClose(self):
        if self.finACK != 1 or self.fin != 1:
            self.sendFin()

    def sendFin(self):
        while True:
            if len(self.TIMER_THREAD.keys()) == 0:
                self.ack.append(self.seqnum + 1)
                self.send(str("\r\n").encode())
                break

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        while True:
            if len(self.buffer) == 0:
                time.sleep(5)
                if len(self.buffer) == 0:
                    self.socket.stoprecv()
                    self.flag = 1
                    break
