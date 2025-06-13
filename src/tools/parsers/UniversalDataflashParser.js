// src/tools/parsers/UniversalDataflashParser.js

export default class UniversalDataflashParser {
    constructor() {
        this.msgFmts = {};
        this.parsedData = {};
    }

    processData(data) {
        const dataView = new DataView(data);
        let offset = 0;

        // First pass: Learn all message formats from the FMT messages
        while (offset < data.byteLength - 3) {
            if (dataView.getUint8(offset) === 0xA3 && dataView.getUint8(offset + 1) === 0x95) {
                if (dataView.getUint8(offset + 2) === 128) { // FMT Message ID
                    this.parseFmtMessage(dataView, offset);
                }
            }
            offset++;
        }

        // Second pass: Parse all data messages
        offset = 0;
        while (offset < data.byteLength - 3) {
            if (dataView.getUint8(offset) === 0xA3 && dataView.getUint8(offset + 1) === 0x95) {
                const msgID = dataView.getUint8(offset + 2);
                if (this.msgFmts[msgID]) {
                    this.parseDataMessage(msgID, dataView, offset);
                }
            }
            offset++;
        }

        this.finalizeDataStructure();
        console.log(`[Universal Parser] Successfully parsed ${Object.keys(this.parsedData).length} message types for the AI backend.`);
        
        // Return the final data object for the worker to handle
        return this.parsedData;
    }

    parseFmtMessage(dataView, offset) {
        try {
            const fmtType = dataView.getUint8(offset + 3);
            const fmtName = this.readString(dataView, offset + 5, 4);
            const fmtFormat = this.readString(dataView, offset + 9, 16);
            const fmtLabels = this.readString(dataView, offset + 25, 64).split(',');
            // --- ADD THIS DEBUG LINE ---
            console.log(`[Parser Debug] Found FMT for: ${fmtName}, Labels: [${fmtLabels.join(', ')}]`);
            // --------------------------
            this.msgFmts[fmtType] = { name: fmtName, len: dataView.getUint8(offset + 4), format: fmtFormat, labels: fmtLabels };
        } catch (e) { /* Ignore parsing errors */ }
    }

    parseDataMessage(msgID, dataView, offset) {
        const fmt = this.msgFmts[msgID];
        if (!fmt || offset + fmt.len > dataView.buffer.byteLength) return;
        let dataOffset = 3;
        const messageData = {};
        for (let i = 0; i < fmt.format.length; i++) {
            const label = fmt.labels[i];
            const type = fmt.format[i];
            try {
                switch (type) {
                    case 'b': messageData[label] = dataView.getInt8(offset + dataOffset); dataOffset += 1; break;
                    case 'B': messageData[label] = dataView.getUint8(offset + dataOffset); dataOffset += 1; break;
                    case 'h': messageData[label] = dataView.getInt16(offset + dataOffset, true); dataOffset += 2; break;
                    case 'H': messageData[label] = dataView.getUint16(offset + dataOffset, true); dataOffset += 2; break;
                    case 'i': messageData[label] = dataView.getInt32(offset + dataOffset, true); dataOffset += 4; break;
                    case 'I': messageData[label] = dataView.getUint32(offset + dataOffset, true); dataOffset += 4; break;
                    case 'q': case 'Q': messageData[label] = Number(dataView.getBigInt64(offset + dataOffset, true)); dataOffset += 8; break;
                    case 'f': messageData[label] = dataView.getFloat32(offset + dataOffset, true); dataOffset += 4; break;
                    case 'd': messageData[label] = dataView.getFloat64(offset + dataOffset, true); dataOffset += 8; break;
                    case 'n': dataOffset += 4; break;
                    case 'N': dataOffset += 16; break;
                    case 'Z': dataOffset += 64; break;
                    case 'M': messageData[label] = dataView.getUint8(offset + dataOffset); dataOffset += 1; break;
                    case 'e': messageData[label] = dataView.getInt32(offset + dataOffset, true) / 100.0; dataOffset += 4; break;
                    case 'E': messageData[label] = dataView.getUint32(offset + dataOffset, true) / 100.0; dataOffset += 4; break;
                    case 'L': messageData[label] = dataView.getInt32(offset + dataOffset, true); dataOffset += 4; break;
                }
            } catch (e) { /* Skip fields that fail */ }
        }
        if (!this.parsedData[fmt.name]) { this.parsedData[fmt.name] = []; }
        this.parsedData[fmt.name].push(messageData);
    }

    finalizeDataStructure() {
        for (const msgType in this.parsedData) {
            const messages = this.parsedData[msgType];
            const finalStruct = {};
            if (messages.length > 0) {
                const allKeys = new Set();
                messages.forEach(msg => Object.keys(msg).forEach(key => allKeys.add(key)));
                allKeys.forEach(key => finalStruct[key] = new Array(messages.length));
                messages.forEach((msg, i) => {
                    allKeys.forEach(key => {
                        finalStruct[key][i] = msg[key] !== undefined ? msg[key] : null;
                    });
                });
            }
            this.parsedData[msgType] = finalStruct;
        }
    }

    readString(dataView, offset, length) {
        let str = '';
        for (let i = 0; i < length; i++) {
            const charCode = dataView.getUint8(offset + i);
            if (charCode === 0) break;
            str += String.fromCharCode(charCode);
        }
        return str;
    }
}