// src/tools/parsers/UniversalMavlinkParser.js

// Import the core MAVLink protocol library
import { mavlink20 as mavlink, MAVLink20Processor as MAVLink } from '../../libs/mavlink'

/**
 * A powerful parser for .tlog (MAVLink) files.
 * This parser uses the full MAVLink protocol definition to decode every
 * packet in the stream and extract all available message types.
 */
export default class UniversalMavlinkParser {
    constructor() {
        // We initialize the MAVLink helper library.
        this.mav = new MAVLink(null, 1, 1);
        // This will store the data grouped by message type.
        this.messagesByType = {};
    }

    /**
     * Processes the .tlog data from an ArrayBuffer and returns the final parsed object.
     * @param {ArrayBuffer} data The raw data from the .tlog file.
     * @returns {object} The fully parsed data object.
     */
    processData(data) {
        // The MAVLink library has a built-in method to process a buffer.
        // The second argument is a callback function that will be executed
        // for every single message that is successfully decoded.
        this.mav.parseBuffer(new Uint8Array(data), (decodedMsg) => {
            if (decodedMsg) {
                // The 'name' property gives us the message type (e.g., 'ATTITUDE')
                const msgName = decodedMsg.name;
                
                // If this is the first time we've seen this message type, create an array for it.
                if (!this.messagesByType[msgName]) {
                    this.messagesByType[msgName] = [];
                }
                
                // Add the decoded message object to the list for its type.
                this.messagesByType[msgName].push(decodedMsg);
            }
        });

        // The data is currently an array-of-objects. We must convert it
        // to the object-of-arrays format the application expects.
        const finalData = this.finalizeDataStructure();
        
        console.log(`[Universal TLog Parser] Successfully parsed ${Object.keys(finalData).length} message types.`);
        return finalData;
    }

    /**
     * Converts the stored data from an array-of-objects to the application's expected
     * format (an object-of-arrays).
     */
    finalizeDataStructure() {
        const finalStruct = {};
        for (const msgType in this.messagesByType) {
            const messages = this.messagesByType[msgType];
            const finalTypeStruct = {};

            if (messages.length > 0) {
                // Get all possible field names from the first message
                const fields = Object.keys(messages[0].fields);
                
                // Initialize an array for each field
                fields.forEach(field => finalTypeStruct[field] = new Array(messages.length));

                // Populate the arrays
                messages.forEach((msg, i) => {
                    fields.forEach(field => {
                        finalTypeStruct[field][i] = msg.fields[field];
                    });
                });
            }
            finalStruct[msgType] = finalTypeStruct;
        }
        return finalStruct;
    }
}