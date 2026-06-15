import struct

class DMU41Parser:
    _message_body_dict_length = {
        #0x01: 2, # built in test start up
        #0x02: 2, # built in test operational

        #0x03: 2, # Error indication flags
        #0x04: 2,
        #0x05: 2,
        #0x06: 2,
        #0x07: 2,

        0x20: 4, # X angular rate
        0x21: 4, # Y angular rate
        0x22: 4, # Z angular rate
        0x29: 4, # X linear acceleration
        0x2A: 4, # Y linear acceleration
        0x2B: 4, # Z linear acceleration
    }
        
    def __init__(self):
        self.state = "WAIT_H1"
        self.buffer = bytearray()
        self.body_size = sum(self._message_body_dict_length.values())
        self.packet_size = 2 + self.body_size + 2 # count + body + checksum

    def parse_byte(self, byte):
        if self.state == "WAIT_H1":
            if byte == 0x55:
                self.state = "WAIT_H2"
            return None
        elif self.state == "WAIT_H2":
            if byte == 0xAA:
                self.state = "READING"
                self.buffer.clear()
            else:
                self.state = "WAIT_H1"
            return None
        
        elif self.state == "READING":
            self.buffer.append(byte)

            if len(self.buffer) < self.packet_size:
                return None
            
            self.state = "WAIT_H1"
            return self._parse_packet(self.buffer)
        
    def parse_byte_essential(self, byte):
        data = self.parse_byte(byte)
        if data is not None:
            return self._return_essential_data(data)
        return None
        
    def _parse_packet(self, packet):
        count = int.from_bytes(packet[0:2], byteorder='big')

        body_bytes = packet[2:2+self.body_size]
        index = 0

        return_body = {
            "error codes": [],
            "data": {},
            "checksum": None
        }

        for key, length in self._message_body_dict_length.items():
            value = body_bytes[index:index+length]
            index += length

            if key > 0x07:
                body = struct.unpack('>f', value)[0]
                return_body["data"][key] = body
                continue

            body = int.from_bytes(value, byteorder='big')
            match key:
                case 0x03: return_body["error codes"].extend(self._error_flagger(body, base_index=1))
                case 0x04: return_body["error codes"].extend(self._error_flagger(body, base_index=17))
                case 0x05: return_body["error codes"].extend(self._error_flagger(body, base_index=33))
                case 0x06: return_body["error codes"].extend(self._error_flagger(body, base_index=49))
                case 0x07: return_body["error codes"].extend(self._error_flagger(body, base_index=65))
        
        checksum = int.from_bytes(packet[2+self.body_size:2+self.body_size+2], byteorder='big')
        return_body["checksum"] = checksum

        return return_body

    def _return_essential_data(self, data):
        return_data = {
            "error codes": data["error codes"],
            "angular rates": {
                "x": data["data"].get(0x20, None),
                "y": data["data"].get(0x21, None),
                "z": data["data"].get(0x22, None),
            },
            "linear accelerations": {
                "x": data["data"].get(0x29, None),
                "y": data["data"].get(0x2A, None),
                "z": data["data"].get(0x2B, None),
            },
        }
        return return_data

    def _error_flagger(self, raw_data, base_index):
        error_flags = []
        for i in range(16):
            if raw_data & (1 << i):
                error_flags.append(base_index + i)
        return error_flags
    

if __name__ == "__main__":
    parser = DMU41Parser()
    test_buffer = [
        0x55, 0xAA,               # Header (2バイト)
        0x00, 0x26,               # Count (2バイト: 38バイトのBody長という想定)
        
        # --- ここから Body (38バイト) ---
        0x00, 0x01,               # 0x01: BIT Start up = 1
        0x00, 0x02,               # 0x02: BIT Operational = 2
        0x00, 0x11,               # 0x03: Error (1-16) -> 0x11は 1番目と5番目のビットが1！
        0x00, 0x00,               # 0x04: Error (17-32) -> エラーなし
        0x00, 0x00,               # 0x05: Error (33-48) -> エラーなし
        0x00, 0x00,               # 0x06: Error (49-64) -> エラーなし
        0x00, 0x00,               # 0x07: Error (65-80) -> エラーなし
        
        0x3F, 0x80, 0x00, 0x00,   # 0x20: X Gyro (Float) -> 1.0 になるビット列
        0xBF, 0x80, 0x00, 0x00,   # 0x21: Y Gyro (Float) -> -1.0 になるビット列
        0x00, 0x00, 0x00, 0x00,   # 0x22: Z Gyro (Float) -> 0.0 になるビット列
        
        0x41, 0x1C, 0xCC, 0xCD,   # 0x29: X Accel (Float) -> 約 9.8 になるビット列
        0x3F, 0x00, 0x00, 0x00,   # 0x2A: Y Accel (Float) -> 0.5 になるビット列
        0xC1, 0x1C, 0xCC, 0xCD,   # 0x2B: Z Accel (Float) -> 約 -9.8 になるビット列
        
        # --- ここまで Body ---
        
        0x12, 0x34                # Checksum (2バイト)
    ]

    for byte in test_buffer:
        result = parser.parse_byte_essential(byte)
        if result is not None:
            print("Parsed Data:", result)