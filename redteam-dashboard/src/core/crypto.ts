
// A pure TypeScript implementation of HMAC-SHA256 that does not rely on Node.js standard library or external native modules.
const uint8Array = Uint8Array;
const uint32Array = Uint32Array;
const pow = Math.pow;

const DEFAULT_STATE = new uint32Array(8);
const ROUND_CONSTANTS: number[] = [];
const M = new uint32Array(64);

function getFractionalBits(n: number) {
  return ((n - (n | 0)) * pow(2, 32)) | 0;
}

let n = 2;
let nPrime = 0;
while (nPrime < 64) {
  let isPrime = true;
  for (let factor = 2; factor <= n / 2; factor++) {
    if (n % factor === 0) {
      isPrime = false;
      break;
    }
  }
  if (isPrime) {
    if (nPrime < 8) {
      DEFAULT_STATE[nPrime] = getFractionalBits(pow(n, 1 / 2));
    }
    ROUND_CONSTANTS[nPrime] = getFractionalBits(pow(n, 1 / 3));
    nPrime++;
  }
  n++;
}

const LittleEndian = !!new uint8Array(new uint32Array([1]).buffer)[0];

function convertEndian(word: number) {
  if (LittleEndian) {
    return (
      (word >>> 24) |
      (((word >>> 16) & 0xff) << 8) |
      (((word >>> 8) & 0xff) << 16) |
      ((word & 0xff) << 24)
    );
  } else {
    return word;
  }
}

function rightRotate(word: number, bits: number) {
  return (word >>> bits) | (word << (32 - bits));
}

function sha256(data: Uint8Array): Uint8Array {
  const STATE = DEFAULT_STATE.slice();
  const length = data.length;
  const bitLength = length * 8;
  const newBitLength = 512 - ((bitLength + 64) % 512) - 1 + bitLength + 65;
  const bytes = new uint8Array(newBitLength / 8);
  const words = new uint32Array(bytes.buffer);
  bytes.set(data, 0);
  bytes[length] = 0b10000000;
  words[words.length - 1] = convertEndian(bitLength);

  let round;
  for (let block = 0; block < newBitLength / 32; block += 16) {
    const workingState = STATE.slice();
    for (round = 0; round < 64; round++) {
      let MRound;
      if (round < 16) {
        MRound = convertEndian(words[block + round]);
      } else {
        const gamma0x = M[round - 15];
        const gamma1x = M[round - 2];
        MRound =
          M[round - 7] +
          M[round - 16] +
          (rightRotate(gamma0x, 7) ^ rightRotate(gamma0x, 18) ^ (gamma0x >>> 3)) +
          (rightRotate(gamma1x, 17) ^ rightRotate(gamma1x, 19) ^ (gamma1x >>> 10));
      }
      M[round] = MRound |= 0;
      const t1 =
        (rightRotate(workingState[4], 6) ^
          rightRotate(workingState[4], 11) ^
          rightRotate(workingState[4], 25)) +
        ((workingState[4] & workingState[5]) ^ (~workingState[4] & workingState[6])) +
        workingState[7] +
        MRound +
        ROUND_CONSTANTS[round];
      const t2 =
        (rightRotate(workingState[0], 2) ^
          rightRotate(workingState[0], 13) ^
          rightRotate(workingState[0], 22)) +
        ((workingState[0] & workingState[1]) ^ (workingState[2] & (workingState[0] ^ workingState[1])));

      for (let i = 7; i > 0; i--) {
        workingState[i] = workingState[i - 1];
      }
      workingState[0] = (t1 + t2) | 0;
      workingState[4] = (workingState[4] + t1) | 0;
    }
    for (round = 0; round < 8; round++) {
      STATE[round] = (STATE[round] + workingState[round]) | 0;
    }
  }

  return new uint8Array(
    new uint32Array(
      STATE.map(val => convertEndian(val))
    ).buffer
  );
}

function hmac(key: Uint8Array, data: Uint8Array): Uint8Array {
  let finalKey = key;
  if (key.length > 64) {
    finalKey = sha256(key);
  }
  if (finalKey.length < 64) {
    const tmp = new Uint8Array(64);
    tmp.set(finalKey, 0);
    finalKey = tmp;
  }

  const innerKey = new Uint8Array(64);
  const outerKey = new Uint8Array(64);
  for (let i = 0; i < 64; i++) {
    innerKey[i] = 0x36 ^ finalKey[i];
    outerKey[i] = 0x5c ^ finalKey[i];
  }

  const msg = new Uint8Array(data.length + 64);
  msg.set(innerKey, 0);
  msg.set(data, 64);

  const result = new Uint8Array(64 + 32);
  result.set(outerKey, 0);
  result.set(sha256(msg), 64);

  return sha256(result);
}

function stringToUtf8Array(str: string): Uint8Array {
  const arr = [];
  for (let i = 0; i < str.length; i++) {
    let charcode = str.charCodeAt(i);
    if (charcode < 0x80) arr.push(charcode);
    else if (charcode < 0x800) {
      arr.push(0xc0 | (charcode >> 6), 0x80 | (charcode & 0x3f));
    }
    else if (charcode < 0xd800 || charcode >= 0xe000) {
      arr.push(0xe0 | (charcode >> 12), 0x80 | ((charcode >> 6) & 0x3f), 0x80 | (charcode & 0x3f));
    }
    else {
      i++;
      charcode = 0x10000 + (((charcode & 0x3ff) << 10) | (str.charCodeAt(i) & 0x3ff));
      arr.push(0xf0 | (charcode >> 18), 0x80 | ((charcode >> 12) & 0x3f), 0x80 | ((charcode >> 6) & 0x3f), 0x80 | (charcode & 0x3f));
    }
  }
  return new Uint8Array(arr);
}

/**
 * Computes HMAC-SHA256 signature for the given data and key.
 * @param data The payload/message string.
 * @param key The secret key string.
 */
export function hmacSHA256(data: string, key: string): string {
  const keyBytes = stringToUtf8Array(key);
  const dataBytes = stringToUtf8Array(data);
  const hashBytes = hmac(keyBytes, dataBytes);
  return Array.from(hashBytes, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Generates a secure random hexadecimal nonce of the specified byte length.
 * @param length The length of the nonce in bytes.
 */
export function generateNonce(length: number = 16): string {
  // CSPRNG — crypto.getRandomValues en vez de Math.random (no criptográficamente seguro)
  const arr = new Uint8Array(length);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(arr);
  } else {
    throw new Error('crypto.getRandomValues no disponible — CSPRNG requerido para nonce');
  }
  return Array.from(arr, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Verifies the integrity of a payload against a given signature and secret key.
 * @param payload The request/response payload string.
 * @param key The secret key string.
 * @param signature The expected HMAC-SHA256 signature in hexadecimal format.
 */
export function verifyIntegrity(payload: string, key: string, signature: string): boolean {
  const computed = hmacSHA256(payload, key);
  return computed === signature;
}
