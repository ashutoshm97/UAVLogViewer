// src/tools/parsers/parser.worker.js (Parallel Processing Final Version)

// Import BOTH parsers
import UniversalDataflashParser from './UniversalDataflashParser.js';
const DataflashParser = require('./JsDataflashParser/parser').default;

// Keep the other parsers for other file types
const mavparser = require('./mavlinkParser');
const DjiParser = require('./djiParser').default;

let parser; // This will hold the instance of the old parser for the UI

// This function sends the complete data from the new parser to the Python backend.
async function sendDataToBackend(parsedData) {
    try {
        await fetch('http://localhost:5000/api/set-flight-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(parsedData)
        });
        console.log("Universal Parser data successfully sent to backend for AI Agent.");
    } catch (error) {
        console.error("Worker failed to send data to backend:", error);
    }
}

self.addEventListener('message', async function (event) {
    if (event.data === null) {
        console.log('Worker received bad file message!');
        return;
    }
    
    if (event.data.action === 'parse') {
        const data = event.data.file;
        
        if (event.data.isTlog) {
            parser = new mavparser.MavlinkParser();
            parser.processData(data);
        } else if (event.data.isDji) {
            parser = new DjiParser();
            await parser.processData(data);
        } else {
            // --- NEW PARALLEL LOGIC FOR .BIN FILES ---
            console.log("Running both old and new parsers in parallel...");

            // 1. Run the NEW Universal Parser for the AI Agent
            const newParser = new UniversalDataflashParser();
            const fullParsedData = newParser.processData(data);

            // --- ADD THIS CRUCIAL DEBUG LINE ---
            // This will print the keys found by the new parser to your BROWSER console.
            console.log("[DEBUG] Keys parsed by Universal Parser:", Object.keys(fullParsedData).sort());
            // ------------------------------------

            // Send its complete data to the Python backend immediately.
            sendDataToBackend(fullParsedData);

            // 2. Run the OLD Parser for the existing UI (NO CHANGES HERE)
            // This parser will post messages back to the main thread as it always has,
            // ensuring the Plotly and Cesium views are not disturbed.
            parser = new DataflashParser(true);
            parser.processData(data, ['CMD', 'MSG', 'FILE', 'MODE', 'AHR2', 'ATT', 'GPS', 'POS',
                'XKQ1', 'XKQ', 'NKQ1', 'NKQ2', 'XKQ2', 'PARM', 'MSG', 'STAT', 'EV', 'XKF4', 'FNCE'])
        }

    } else if (event.data.action === 'loadType') {
        // This is the guard clause. If the parser object hasn't been created yet,
        // just ignore this request and exit the function.
        if (!parser) {
            console.log('Parser not yet initialized, ignoring loadType request.');
            return; 
        }
        
        // If the parser *does* exist, proceed as normal.
        parser.loadType(event.data.type.split('[')[0]);
    }
});