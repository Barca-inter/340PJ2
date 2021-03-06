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
        # self.NagleBuffer = b''
        # self.fin = 0  # initialize the fin signal
        # self.finACK = 0  # initialize the ACK of fin
        self.flag = 1
        self.nagleEnd = 0
        # self.secfin = 0
        self.retranHeader = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.executor.submit(self.listener)
        self.executor.submit(self.nagle)

    def nagle(self) -> None:
        # print("a")
        while self.nagleEnd == 0:
            # print("b")
            temp = self.data
            # print("self.data",self.data)
            time.sleep(0.25)
            if temp == self.data and temp != b'':
                self.nagleEnd = 1
                self.send(temp)
                # print("c")
                break

    def listener(self) -> None:
        # print(self.flag)
        while self.flag == 1:
            # print("a")
            ss, addr = self.socket.recvfrom()
            # print("b")
            if addr == ("", 0):
                # print(self.flag)
                # print("c")
                break
            if len(ss) <= 34:  # if receive ACK, STOP corresponding TIMER
                # print("e")
                cmd = "!H32s"
                # print("收到ss:",ss)
                this_ack, ackchsm = struct.unpack(cmd, ss)
                # print("收到this_ack:",this_ack)
                rcv_csm = self.getchecksum(str(this_ack).encode()).encode()
                # print("计算rcv_csm:",rcv_csm)
                # print("收到ackhsm：",ackchsm)
                if rcv_csm == ackchsm:
                    # print("收到ACK chsm: == ")
                    self.ack.append(this_ack)
                    # print("ack:", self.ack)
                    if this_ack == 0:
                        self.finACK = 1
                    # print("f")
                else:
                    continue
                    # print("不等rec:",rcv_csm," & ",ackchsm)

            else:  # if receive DATA, put into buffer
                # print("g")
                cmd = "!H32s" + str(len(ss) - 34) + "s"
                header_sq, chsm, data = struct.unpack(cmd, ss)
                # print("receive data header",header_sq)
                # print("receive data :",data)
                # print("Got header is %d" % header)

                # if checksum is wrong, drop the packet, resend
                databody = str(header_sq).encode() + data
                recv_chsm = self.getchecksum(databody).encode()
                # print("databody",databody)
                # print("chsm:",chsm)
                # print("recv_chsm",recv_chsm)

                if recv_chsm != chsm:
                    # print("recv_chsm != chsm")
                    continue
                if recv_chsm == chsm:
                    # print("h")
                    # print("recv_chsm == chsm")
                    if header_sq < self.recvnum:
                        # print("header<recvnum, recvnum is ", self.recvnum)
                        ack = struct.pack("!H32s", header_sq, self.getchecksum(str(header_sq).encode()).encode()) #--ack = struct.pack("!H", header_sq)
                        # print("多余ack",header_sq)
                        # self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                    else:

                        self.buffer.update({header_sq: data})
                        # print("buffer.update::::", self.buffer)
                        # print("buffer update header:",header_sq)
                        ack = struct.pack("!H32s", header_sq, self.getchecksum(str(header_sq).encode()).encode()) #ack = struct.pack("!H", header_sq)
                        # print("buffer:",self.buffer)
                    # print("发送ack", header_sq)
                    self.socket.sendto(ack, (self.dst_ip, self.dst_port))
                    # print("i")
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
            # print("重发", header)
            self.socket.sendto(ss, (self.dst_ip, self.dst_port))
            time.sleep(0.5)
            self.retransmission(ss)
            # t2 = Timer(0.5, self.retransmission, (ss,))  # self.seqnum,
            # if dt != str("\r\n").encode():
            #     self.TIMER_THREAD.update({header: t2})
            # t2.start()
        else:
            self.ack.remove(header)
            # print("丢：",header)
            # if dt == str("\r\n").encode():
            #     if self.finACK != 1:
            #         time.sleep(1)
            #         self.retransmission(ss)
            # else:

            self.TIMER_THREAD.pop(header)

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!

        raw_data = data_bytes
        # self.data += raw_data
        if len(self.data) + len(raw_data) <= 1438 and self.nagleEnd == 0:
            self.data += raw_data
            return None
        if self.nagleEnd == 1:
            self.data = raw_data
        # if self.data == b'':
        #     self.data = raw_data
        # print("all data:", self.data)

        while True:

            # if len(raw_data) > 1438:
            if len(self.data) > 1438:
                # packet_data_bytes = raw_data[0:1438]  # !python note: range needs to cover the higher index
                packet_data_bytes = self.data[0:1438]
                # raw_data = raw_data[1438:]
                raw_data = self.data[1438:]
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

                # if len(raw_data) != 0:
                if len(self.data) != 0:
                    self.seqnum += 1
                    # self.retranHeader.update({self.seqnum:1})
                    # cmd = "!H32s" + str(len(raw_data)) + "s"
                    cmd = "!H32s" + str(len(self.data)) + "s"
                    # databody = str(self.seqnum).encode() + raw_data
                    databody = str(self.seqnum).encode() + self.data
                    chks = self.getchecksum(databody).encode()
                    # ss = struct.pack(cmd, self.seqnum, chks, raw_data)
                    ss = struct.pack(cmd, self.seqnum, chks, self.data)
                    self.socket.sendto(ss, (self.dst_ip, self.dst_port))
                    t = Timer(0.5, self.retransmission, (ss,))
                    if raw_data != str("\r\n").encode():
                        self.TIMER_THREAD.update({self.seqnum: t})
                    t.start()
                    time.sleep(0.1)
                    # raw_data = b''
            if len(raw_data) > 1438 and self.data == b'':
                # print("111")
                self.data = raw_data
                continue
            self.data = raw_data
            raw_data = b''
            # print("remain",self.data)
            if self.nagleEnd == 1:
                self.data = b''
            if len(self.data) == 0:
                # print("send end")
                break


    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        rs = ''

        while True:
            if self.buffer == {}:
                continue

            m = max(self.buffer.keys())
            for i in range(self.recvnum, m+1):
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

    # def SecondClose(self):
    #     if self.finACK != 1 or self.fin != 1:
    #         self.sendFin()
    #
    # def sendFin(self):
    #     while True:
    #         if len(self.TIMER_THREAD.keys()) == 0:
    #             self.ack.append(self.seqnum + 1)
    #             self.send(str("\r\n").encode())
    #             break

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        while True:
            # print("self.buffer",self.buffer)
            if len(self.buffer) == 0:
                time.sleep(5)
                # print("self.buffer", self.buffer)
                if len(self.buffer) == 0:
                    self.socket.stoprecv()
                    self.flag = 0
                    self.nagleEnd = 1
                    break
