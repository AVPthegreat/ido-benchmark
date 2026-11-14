
  public add(obj: any) {
    let packet;
    if (typeof obj === "string") {
      packet = this.decodeString(obj);
      if (
        packet.type === PacketType.BINARY_EVENT ||
        packet.type === PacketType.BINARY_ACK
      ) {
        // binary packet's json
        this.reconstructor = new BinaryReconstructor(packet);

        // no attachments, labeled binary but no binary data to follow
        if (packet.attachments === 0) {
          super.emit("decoded", packet);
        }
      } else {
        // non-binary full packet
        super.emit("decoded", packet);
      }
    } else if (isBinary(obj) || obj.base64) {
      // raw binary data
      if (!this.reconstructor) {
        throw new Error("got binary data when not reconstructing a packet");
      } else {
        packet = this.reconstructor.takeBinaryData(obj);
        if (packet) {
          // received final buffer
          this.reconstructor = null;
          super.emit("decoded", packet);
        }
      }
    } else {
      throw new Error("Unknown type: " + obj);
    }
  }

  /**
   * Decode a packet String (JSON data)
   *
   * @param {String} str
   * @return {Object} packet
   */
  private decodeString(str): Packet {
    let i = 0;
    // look up type
    const p: any = {
      type: Number(str.charAt(0)),
    };

    if (PacketType[p.type] === undefined) {
      throw new Error("unknown packet type " + p.type);
    }

    // look up attachments if type binary
    if (
      p.type === PacketType.BINARY_EVENT ||
      p.type === PacketType.BINARY_ACK
    ) {
      const start = i + 1;
      while (str.charAt(++i) !== "-" && i != str.length) {}
      const buf = str.substring(start, i);
      if (buf != Number(buf) || str.charAt(i) !== "-") {
        throw new Error("Illegal attachments");
      }
      p.attachments = Number(buf);
    }

    // look up namespace (if any)
    if ("/" === str.charAt(i + 1)) {
      const start = i + 1;
      while (++i) {
        const c = str.charAt(i);
        if ("," === c) break;
        if (i === str.length) break;
      }
      p.nsp = str.substring(start, i);
    } else {
      p.nsp = "/";
    }

    // look up id
    const next = str.charAt(i + 1);
    if ("" !== next && Number(next) == next) {
      const start = i + 1;
      while (++i) {
        const c = str.charAt(i);
        if (null == c || Number(c) != c) {
          --i;
          break;
        }
        if (i === str.length) break;
      }
      p.id = Number(str.substring(start, i + 1));
    }

    // look up json data
    if (str.charAt(++i)) {
      const payload = tryParse(str.substr(i));
      if (Decoder.isPayloadValid(p.type, payload)) {
        p.data = payload;
      } else {
        throw new Error("invalid payload");
      }
    }

    debug("decoded %s as %j", str, p);
    return p;
  }

  private static isPayloadValid(type: PacketType, payload: any): boolean {
    switch (type) {
      case PacketType.CONNECT:
        return typeof payload === "object";
      case PacketType.DISCONNECT:
        return payload === undefined;
      case PacketType.CONNECT_ERROR:
        return typeof payload === "string" || typeof payload === "object";
      case PacketType.EVENT:
      case PacketType.BINARY_EVENT:
        return Array.isArray(payload) && typeof payload[0] === "string";
      case PacketType.ACK:
      case PacketType.BINARY_ACK:
        return Array.isArray(payload);
    }
  }

  /**
   * Deallocates a parser's resources
   */
  public destroy() {
    if (this.reconstructor) {
      this.reconstructor.finishedReconstruction();
    }
  }
}

function tryParse(str) {
  try {
    return JSON.parse(str);
  } catch (e) {
    return false;
  }
}

/**
 * A manager of a binary event's 'buffer sequence'. Should
 * be constructed whenever a packet of type BINARY_EVENT is
 * decoded.
 *
 * @param {Object} packet
 * @return {BinaryReconstructor} initialized reconstructor
 */

class BinaryReconstructor {
  private reconPack;
  private buffers: Array<Buffer | ArrayBuffer> = [];

  constructor(readonly packet: Packet) {
    this.reconPack = packet;
  }
