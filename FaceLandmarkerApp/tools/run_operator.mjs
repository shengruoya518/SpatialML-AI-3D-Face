// Executes the exact JavaScript operator sources for host validation.
import fs from 'node:fs';
import vm from 'node:vm';
import readline from 'node:readline';
const lines = readline.createInterface({ input: process.stdin });
for await (const line of lines) {
    const request = JSON.parse(line);
    for (const values of Object.values(request.tensors)) {
        for (let i = 0; i < values.length; ++i) if (typeof values[i] === 'string') values[i] = Number(values[i]);
    }
    try {
        const context = vm.createContext(request.tensors);
        vm.runInContext(fs.readFileSync(request.script, 'utf8'), context, { timeout: 5000 });
        process.stdout.write(JSON.stringify({ tensors: request.tensors }, (_, value) =>
            typeof value === 'number' && !Number.isFinite(value) ? String(value) : value) + String.fromCharCode(10));
    } catch (error) {
        process.stdout.write(JSON.stringify({ error: String(error) }) + String.fromCharCode(10));
    }
}
