#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acoustic Finite Geometry Transport Layer (AFGTL)
An Acoustic Covert Channel Modem built using Projective Planes, 
Steiner Systems, and Block Codes.

Designed for Phrack Magazine submission compliance.
"""

import argparse
import os
import sys
import zlib
import numpy as np
import scipy.io.wavfile as wav

# =====================================================================
# GLOBAL HARDWARE CONSTANTS
# =====================================================================
FS = 48000
T_S = 0.05
SECRET_KEY = "SINGER"
FREQS = [17000, 17500, 18000, 18500]

def xor_cipher(text, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

def get_singer_sequence(q):
    sets = {
        2: [0, 1, 3],
        3: [0, 1, 3, 9],
        5: [0, 1, 3, 8, 12, 18],
        7: [0, 1, 3, 13, 32, 36, 43, 52]
    }
    v = q**2 + q + 1
    seq = [0] * v
    base_set = sets.get(q)
    if base_set:
        for pos in base_set:
            seq[pos % v] = 1
    return seq

# =====================================================================
# SEGMENTED ENGINES (NO INTER-MODE CODE BLEED ALLOWED)
# =====================================================================

class HammingEngine:
    """Hamming code logic"""
    @staticmethod
    def encode(bits_4):
        d = bits_4
        p1 = d[0] ^ d[1] ^ d[3]
        p2 = d[0] ^ d[2] ^ d[3]
        p3 = d[1] ^ d[2] ^ d[3]
        return [p1, p2, d[0], p3, d[1], d[2], d[3]]

    @staticmethod
    def decode(bits_7):
        b = bits_7.copy()
        s1 = b[0] ^ b[2] ^ b[4] ^ b[6]
        s2 = b[1] ^ b[2] ^ b[5] ^ b[6]
        s3 = b[3] ^ b[4] ^ b[5] ^ b[6]
        syn = s1 + (s2 * 2) + (s3 * 4)
        if syn != 0:
            b[syn - 1] = 1 - b[syn - 1]
        return [b[2], b[4], b[5], b[6]]

    @staticmethod
    def string_to_bits(text):
        all_bits = []
        for char in text:
            b = [int(x) for x in bin(ord(char))[2:].zfill(8)]
            n1 = HammingEngine.encode(b[:4])
            n2 = HammingEngine.encode(b[4:])
            all_bits.extend([n1[0], n2[0], n1[1], n2[1], n1[2], n2[2], n1[3], n2[3], 
                             n1[4], n2[4], n1[5], n2[5], n1[6], n2[6]])
        return all_bits

    @staticmethod
    def bits_to_string(bits):
        chars = []
        for i in range(0, len(bits), 14):
            if i + 14 > len(bits): break
            chunk = bits[i:i+14]
            h1 = [chunk[0], chunk[2], chunk[4], chunk[6], chunk[8], chunk[10], chunk[12]]
            h2 = [chunk[1], chunk[3], chunk[5], chunk[7], chunk[9], chunk[11], chunk[13]]
            byte_val = int("".join(map(str, HammingEngine.decode(h1) + HammingEngine.decode(h2))), 2)
            chars.append(chr(byte_val))
        return "".join(chars)

class SDEngine:
    """Extended Hamming code logic"""
    @staticmethod
    def extended_hamming_84_encode(bits_4):
        """Self-Dual [8,4,4] Code."""
        d = bits_4
        p1 = d[0] ^ d[1] ^ d[3]
        p2 = d[0] ^ d[2] ^ d[3]
        p3 = d[1] ^ d[2] ^ d[3]
        h7 = [p1, p2, d[0], p3, d[1], d[2], d[3]]
        p_ext = sum(h7) % 2
        return h7 + [p_ext]
    
    @staticmethod
    def extended_hamming_84_decode(bits_8):
        """Self-Dual [8,4,4] decoder."""
        b7 = bits_8[:7]
        p_ext = bits_8[7]
        s1 = b7[0] ^ b7[2] ^ b7[4] ^ b7[6]
        s2 = b7[1] ^ b7[2] ^ b7[5] ^ b7[6]
        s3 = b7[3] ^ b7[4] ^ b7[5] ^ b7[6]
        syn = s1 + (s2 * 2) + (s3 * 4)
        actual_parity = sum(b7) % 2
        if syn != 0 and actual_parity != p_ext:
            b7[syn - 1] = 1 - b7[syn - 1]
        return [b7[2], b7[4], b7[5], b7[6]]

    @staticmethod
    def string_to_bits_selfdual(text):
        all_bits = []
        for char in text:
            b = [int(x) for x in bin(ord(char))[2:].zfill(8)]
            # Two blocks of 8 bits = 16 bits per character
            all_bits.extend(SDEngine.extended_hamming_84_encode(b[:4]))
            all_bits.extend(SDEngine.extended_hamming_84_encode(b[4:]))
        return all_bits

    @staticmethod
    def bits_to_string_selfdual(bits):
        chars = []
        for i in range(0, len(bits), 16): # Stride fixed at 16
            if i + 16 > len(bits): break
            chunk = bits[i:i+16]
            try:
                n1 = SDEngine.extended_hamming_84_decode(chunk[:8])
                n2 = SDEngine.extended_hamming_84_decode(chunk[8:])
                val = int("".join(map(str, n1 + n2)), 2)
                chars.append(chr(val))
            except: continue
        return "".join(chars)
    
    string_to_bits = string_to_bits_selfdual
    bits_to_string = bits_to_string_selfdual

class QREngine:
    """Quadratic residue code logic"""
    @staticmethod
    def qr_73_encode(bits_3):
        """Quadratic Residue Code mod 7."""
        d = bits_3
        p1 = d[0] ^ d[1]
        p2 = d[1] ^ d[2]
        p3 = d[0] ^ d[2]
        p4 = d[0] ^ d[1] ^ d[2]
        return [d[0], d[1], d[2], p1, p2, p3, p4]
    
    @staticmethod
    def qr_73_decode(bits_7):
        """True Quadratic Residue [7,3,4] Syndrome Decoder with error correction."""
        b = bits_7.copy() if isinstance(bits_7, list) else list(bits_7)
        
        # Recalculate parity check bits from received data bits
        s1 = b[3] ^ (b[0] ^ b[1])
        s2 = b[4] ^ (b[1] ^ b[2])
        s3 = b[5] ^ (b[0] ^ b[2])
        s4 = b[6] ^ (b[0] ^ b[1] ^ b[2])
        
        # Map the unique syndrome configuration to the corrupted bit index
        syndrome = (s1, s2, s3, s4)
        
        # Syndrome look-up dictionary for [7,3,4] cyclic generator matrix
        error_patterns = {
            (1, 0, 0, 0): 3,  # Parity bit 1 error
            (0, 1, 0, 0): 4,  # Parity bit 2 error
            (0, 0, 1, 0): 5,  # Parity bit 3 error
            (0, 0, 0, 1): 6,  # Parity bit 4 error
            (1, 0, 1, 1): 0,  # Data bit 1 error
            (1, 1, 0, 1): 1,  # Data bit 2 error
            (0, 1, 1, 1): 2   # Data bit 3 error
        }
        
        # If the syndrome matches a known error pattern, flip the corrupted bit
        if syndrome in error_patterns:
            idx = error_patterns[syndrome]
            b[idx] = 1 - b[idx]
            
        return b[:3]

    @staticmethod
    def string_to_bits_qr_multi(text):
        """String -> ASCII -> Three QR Blocks + 1 bit Padding (22 bits/char)."""
        all_bits = []
        for char in text:
            # 8 bits ASCII + 1 bit internal padding = 9 bits base
            b = [int(x) for x in bin(ord(char))[2:].zfill(8)] + [0]
            # 3 blocks * 7 bits = 21 bits + 1 extra trailing pad bit = 22 bits total
            all_bits.extend(QREngine.qr_73_encode(b[:3]))
            all_bits.extend(QREngine.qr_73_encode(b[3:6]))
            all_bits.extend(QREngine.qr_73_encode(b[6:9]))
            all_bits.append(0) # The 22nd alignment bit
        return all_bits

    @staticmethod
    def bits_to_string_qr_multi(bits):
        """Bits -> Strip 22nd bit -> Decode Three QR Blocks -> ASCII."""
        chars = []
        stride = 22 # Stride fixed at 22 for 4-Ary alignment
        for i in range(0, len(bits), stride):
            if i + stride > len(bits): break
            chunk = bits[i:i+stride]
            try:
                n1 = QREngine.qr_73_decode(chunk[:7])
                n2 = QREngine.qr_73_decode(chunk[7:14])
                n3 = QREngine.qr_73_decode(chunk[14:21])
                # Drop the 9th bit padding, keep original 8-bit ASCII byte
                val = int("".join(map(str, (n1 + n2 + n3)[:8])), 2)
                chars.append(chr(val))
            except: continue
        return "".join(chars)
    
    string_to_bits = string_to_bits_qr_multi
    bits_to_string = bits_to_string_qr_multi

class PG23Engine:
    """Projective place over F_3 code logic"""
    @staticmethod
    def pg23_encode(bits_9):
        """
        Encodes 9 data bits into a 13-bit codeword using the geometric 
        incidence parity constraints of the PG(2,3) Projective Plane.
        """
        d = bits_9
        
        # 4 Parity checks derived from the intersecting lines of the ternary plane
        p0 = d[0] ^ d[1] ^ d[3] ^ d[6]
        p1 = d[1] ^ d[2] ^ d[4] ^ d[7]
        p2 = d[2] ^ d[3] ^ d[5] ^ d[8]
        p3 = d[0] ^ d[4] ^ d[5] ^ d[6] ^ d[7]  # Tail intersection check
        
        # Return Systematic Codeword: 9 Data bits + 4 Parity bits
        return d + [p0, p1, p2, p3]

    @staticmethod
    def pg23_decode(bits_13):
        """
        Decodes 13 received bits back into 9 data bits by calculating 
        the syndrome across the plane's geometric line intersections.
        """
        b = bits_13.copy() if isinstance(bits_13, list) else list(bits_13)
        
        # Recalculate parity check syndromes
        s0 = b[9]  ^ (b[0] ^ b[1] ^ b[3] ^ b[6])
        s1 = b[10] ^ (b[1] ^ b[2] ^ b[4] ^ b[7])
        s2 = b[11] ^ (b[2] ^ b[3] ^ b[5] ^ b[8])
        s3 = b[12] ^ (b[0] ^ b[4] ^ b[5] ^ b[6] ^ b[7])
        
        syndrome = (s0, s1, s2, s3)
        
        # Geometric syndrome lookup table for PG(2,3) point corruption
        error_patterns = {
            (1, 0, 0, 0): 9,   # Parity 0 error
            (0, 1, 0, 0): 10,  # Parity 1 error
            (0, 0, 1, 0): 11,  # Parity 2 error
            (0, 0, 0, 1): 12,  # Parity 3 error
            (1, 0, 0, 1): 0,   # Data 0 error
            (1, 1, 0, 0): 1,   # Data 1 error
            (0, 1, 1, 0): 2,   # Data 2 error
            (1, 0, 1, 0): 3,   # Data 3 error
            (0, 1, 0, 1): 4,   # Data 4 error
            (0, 0, 1, 1): 5,   # Data 5 error
            (1, 0, 0, 1): 6,   # Data 6 error
            (0, 1, 0, 1): 7,   # Data 7 error
            (0, 0, 1, 0): 8    # Data 8 error
        }
        
        if syndrome in error_patterns:
            idx = error_patterns[syndrome]
            b[idx] = 1 - b[idx]
            
        return b[:9]

    @staticmethod
    def string_to_bits_pg23(text):
        """Packs text into 9-bit chunks, expands to 13-bit blocks, pads to 14 bits for 4-Ary."""
        all_bits = []
        # Convert entire string to a continuous stream of raw bits
        raw_stream = []
        for char in text:
            raw_stream.extend([int(x) for x in bin(ord(char))[2:].zfill(8)])
            
        # Break stream into 9-bit data blocks
        for i in range(0, len(raw_stream), 9):
            chunk = raw_stream[i:i+9]
            if len(chunk) < 9:
                chunk = chunk + [0] * (9 - len(chunk)) # Zero pad trailing end
                
            encoded_13 = PG23Engine.pg23_encode(chunk)
            # Add 1 alignment bit to make it 14 bits (exactly 7 4-Ary symbols)
            all_bits.extend(encoded_13 + [0])
            
        return all_bits

    @staticmethod
    def bits_to_string_pg23(bits):
        """Unrolls 14-bit strides, extracts 13-bit PG blocks, decodes to standard ASCII bytes."""
        raw_stream = []
        stride = 14
        for i in range(0, len(bits), stride):
            if i + stride > len(bits): break
            chunk = bits[i:i+13] # Drop the 14th alignment bit
            decoded_9 = PG23Engine.pg23_decode(chunk)
            raw_stream.extend(decoded_9)
            
        # Reconstruct 8-bit characters
        chars = []
        for i in range(0, len(raw_stream), 8):
            if i + 8 > len(raw_stream): break
            byte_bits = raw_stream[i:i+8]
            val = int("".join(map(str, byte_bits)), 2)
            chars.append(chr(val))
            
        return "".join(chars)
    
    string_to_bits = string_to_bits_pg23
    bits_to_string = bits_to_string_pg23

class STS9Engine:
    """Steiner triple system on 9 points code"""
    @staticmethod
    def sts9_encode(bits_5):
        """
        Encodes 5 data bits into a 9-bit codeword using the 
        parallel line constraints of an STS(9) Affine System.
        """
        d = bits_5
        
        # 4 Geometric parities built from parallel classes
        p0 = d[0] ^ d[1] ^ d[2]
        p1 = d[1] ^ d[3] ^ d[4]
        p2 = d[0] ^ d[3] ^ d[4]
        p3 = d[2] ^ d[3] ^ d[0]
        
        return d + [p0, p1, p2, p3]

    @staticmethod
    def sts9_decode(bits_9):
        """
        Decodes 9 received bits back into 5 data bits using 
        affine intersection syndromes.
        """
        b = bits_9.copy() if isinstance(bits_9, list) else list(bits_9)
        
        # Recalculate parity intersections
        s0 = b[5] ^ (b[0] ^ b[1] ^ b[2])
        s1 = b[6] ^ (b[1] ^ b[3] ^ b[4])
        s2 = b[7] ^ (b[0] ^ b[3] ^ b[4])
        s3 = b[8] ^ (b[2] ^ b[3] ^ b[0])
        
        syndrome = (s0, s1, s2, s3)
        
        # Error pattern location dictionary for the 9-element affine layout
        error_patterns = {
            (1, 0, 0, 0): 5,  # Parity 0 error
            (0, 1, 0, 0): 6,  # Parity 1 error
            (0, 0, 1, 0): 7,  # Parity 2 error
            (0, 0, 0, 1): 8,  # Parity 3 error
            (1, 0, 1, 1): 0,  # Data 0 error
            (1, 1, 0, 0): 1,  # Data 1 error
            (1, 0, 0, 1): 2,  # Data 2 error
            (0, 1, 1, 1): 3,  # Data 3 error
            (0, 1, 1, 0): 4   # Data 4 error
        }
        
        if syndrome in error_patterns:
            idx = error_patterns[syndrome]
            b[idx] = 1 - b[idx]
            
        return b[:5]

    @staticmethod
    def string_to_bits_sts9(text):
        """Packs text into 5-bit chunks, encodes to 9-bit blocks, pads to 10 bits for 4-Ary alignment."""
        raw_stream = []
        for char in text:
            raw_stream.extend([int(x) for x in bin(ord(char))[2:].zfill(8)])
            
        all_bits = []
        for i in range(0, len(raw_stream), 5):
            chunk = raw_stream[i:i+5]
            if len(chunk) < 5:
                chunk = chunk + [0] * (5 - len(chunk))
                
            encoded_9 = STS9Engine.sts9_encode(chunk)
            # Add 1 alignment bit to make it exactly 10 bits (5 4-Ary symbols)
            all_bits.extend(encoded_9 + [0])
            
        return all_bits

    @staticmethod
    def bits_to_string_sts9(bits):
        """Unrolls 10-bit strides, decodes 9-bit blocks via STS(9) syndrome logic, gathers ASCII bytes."""
        raw_stream = []
        stride = 10
        for i in range(0, len(bits), stride):
            if i + stride > len(bits): break
            chunk = bits[i:i+9]
            decoded_5 = STS9Engine.sts9_decode(chunk)
            raw_stream.extend(decoded_5)
            
        chars = []
        for i in range(0, len(raw_stream), 8):
            if i + 8 > len(raw_stream): break
            byte_bits = raw_stream[i:i+8]
            val = int("".join(map(str, byte_bits)), 2)
            chars.append(chr(val))
            
        return "".join(chars)
    
    string_to_bits = string_to_bits_sts9
    bits_to_string = bits_to_string_sts9

class STS15Engine:
    """Steiner triple system in 15 points code"""
    @staticmethod
    def sts15_encode(bits_11):
        """
        Encodes 11 data bits into a 15-bit codeword using the 
        3D geometric line equations of the PG(3,2) projective space.
        """
        d = bits_11
        
        # 4 Parity checks tracking the 3D intersections of the space
        p0 = d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[7]
        p1 = d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[8]
        p2 = d[2] ^ d[3] ^ d[4] ^ d[6] ^ d[9]
        p3 = d[0] ^ d[3] ^ d[5] ^ d[6] ^ d[10]
        
        return d + [p0, p1, p2, p3]

    @staticmethod
    def sts15_decode(bits_15):
        """
        Decodes 15 received bits back into 11 data bits using 
        3D space syndrome extraction.
        """
        b = bits_15.copy() if isinstance(bits_15, list) else list(bits_15)
        
        # Compute 3D syndromes
        s0 = b[11] ^ (b[0] ^ b[1] ^ b[2] ^ b[4] ^ b[7])
        s1 = b[12] ^ (b[1] ^ b[2] ^ b[3] ^ b[5] ^ b[8])
        s2 = b[13] ^ (b[2] ^ b[3] ^ b[4] ^ b[6] ^ b[9])
        s3 = b[14] ^ (b[0] ^ b[3] ^ b[5] ^ b[6] ^ b[10])
        
        syndrome = (s0, s1, s2, s3)
        
        # Map the 3D geometric syndrome configuration to the corrupt node index
        error_patterns = {
            (1, 0, 0, 0): 11, (0, 1, 0, 0): 12, (0, 0, 1, 0): 13, (0, 0, 0, 1): 14, # Parity fails
            (1, 0, 0, 1): 0,  (1, 1, 0, 0): 1,  (1, 1, 1, 0): 2,  (0, 1, 1, 1): 3,  # Data node fixes
            (1, 0, 1, 0): 4,  (0, 1, 0, 1): 5,  (0, 0, 1, 1): 6,  (1, 0, 0, 0): 7,
            (0, 1, 0, 0): 8,  (0, 0, 1, 0): 9,  (0, 0, 0, 1): 10
        }
        
        if syndrome in error_patterns:
            idx = error_patterns[syndrome]
            b[idx] = 1 - b[idx]
            
        return b[:11]

    @staticmethod
    def string_to_bits_sts15(text):
        """Packs stream into 11-bit segments, expands to 15-bit blocks, pads to 16-bit strides."""
        raw_stream = []
        for char in text:
            raw_stream.extend([int(x) for x in bin(ord(char))[2:].zfill(8)])
            
        all_bits = []
        for i in range(0, len(raw_stream), 11):
            chunk = raw_stream[i:i+11]
            if len(chunk) < 11:
                chunk = chunk + [0] * (11 - len(chunk))
                
            encoded_15 = STS15Engine.sts15_encode(chunk)
            # Add 1 alignment bit to create a perfect 16-bit block (exactly 8 4-Ary symbols)
            all_bits.extend(encoded_15 + [0])
            
        return all_bits

    @staticmethod
    def bits_to_string_sts15(bits):
        """Unrolls 16-bit strides down to 15-bit blocks, resolves 3D syndromes, outputs ASCII string."""
        raw_stream = []
        stride = 16
        for i in range(0, len(bits), stride):
            if i + stride > len(bits): break
            chunk = bits[i:i+15]
            decoded_11 = STS15Engine.sts15_decode(chunk)
            raw_stream.extend(decoded_11)
            
        chars = []
        for i in range(0, len(raw_stream), 8):
            if i + 8 > len(raw_stream): break
            byte_bits = raw_stream[i:i+8]
            val = int("".join(map(str, byte_bits)), 2)
            chars.append(chr(val))
            
        return "".join(chars)
    
    string_to_bits = string_to_bits_sts15
    bits_to_string = bits_to_string_sts15

class SQS16Engine:
    """Isolate your exact functional [16,11,4] 3-Design logic here"""
    @staticmethod
    def encode(bits_11):
        d = bits_11
        p0 = d[0] ^ d[1] ^ d[2] ^ d[4] ^ d[7]
        p1 = d[1] ^ d[2] ^ d[3] ^ d[5] ^ d[8]
        p2 = d[2] ^ d[3] ^ d[4] ^ d[6] ^ d[9]
        p3 = d[0] ^ d[3] ^ d[5] ^ d[6] ^ d[10]
        p4 = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6] ^ d[7] ^ d[8] ^ d[9] ^ d[10] ^ p0 ^ p1 ^ p2 ^ p3
        return d + [p0, p1, p2, p3, p4]

    @staticmethod
    def decode(bits_16):
        b = bits_16.copy()
        s0 = b[11] ^ (b[0] ^ b[1] ^ b[2] ^ b[4] ^ b[7])
        s1 = b[12] ^ (b[1] ^ b[2] ^ b[3] ^ b[5] ^ b[8])
        s2 = b[13] ^ (b[2] ^ b[3] ^ b[4] ^ b[6] ^ b[9])
        s3 = b[14] ^ (b[0] ^ b[3] ^ b[5] ^ b[6] ^ b[10])
        s4 = b[15] ^ (b[0] ^ b[1] ^ b[2] ^ b[3] ^ b[4] ^ b[5] ^ b[6] ^ b[7] ^ b[8] ^ b[9] ^ b[10] ^ b[11] ^ b[12] ^ b[13] ^ b[14])
        syndrome = (s0, s1, s2, s3, s4)
        error_patterns = {
            (1, 0, 0, 0, 1): 11, (0, 1, 0, 0, 1): 12, (0, 0, 1, 0, 1): 13, (0, 0, 0, 1, 1): 14, (0, 0, 0, 0, 1): 15,
            (1, 0, 0, 1, 1): 0,  (1, 1, 0, 0, 1): 1,  (1, 1, 1, 0, 1): 2,  (0, 1, 1, 1, 1): 3,
            (1, 0, 1, 0, 1): 4,  (0, 1, 0, 1, 1): 5,  (0, 0, 1, 1, 1): 6,  (1, 0, 0, 0, 1): 7,
            (0, 1, 0, 0, 1): 8,  (0, 0, 1, 0, 1): 9,  (0, 0, 0, 1, 1): 10
        }
        if syndrome in error_patterns:
            b[error_patterns[syndrome]] = 1 - b[error_patterns[syndrome]]
        return b[:11]

    @staticmethod
    def string_to_bits(text):
        raw_stream = []
        for char in text: raw_stream.extend([int(x) for x in bin(ord(char))[2:].zfill(8)])
        all_bits = []
        for i in range(0, len(raw_stream), 11):
            chunk = raw_stream[i:i+11]
            if len(chunk) < 11: chunk = chunk + [0] * (11 - len(chunk))
            all_bits.extend(SQS16Engine.encode(chunk))
        return all_bits

    @staticmethod
    def bits_to_string(bits):
        raw_stream = []
        for i in range(0, len(bits), 16):
            if i + 16 > len(bits): break
            raw_stream.extend(SQS16Engine.decode(bits[i:i+16]))
        chars = []
        for i in range(0, len(raw_stream), 8):
            if i + 8 > len(raw_stream): break
            val = int("".join(map(str, raw_stream[i:i+8])), 2)
            chars.append(chr(val))
        return "".join(chars)

# =====================================================================
# COMMON PHYSICAL ACOUSTIC MODULATION CORES
# =====================================================================

def modulate_4ary(bits):
    if len(bits) % 2 != 0: bits.append(0)
    samples_per_sym = int(T_S * FS)
    signal = np.array([], dtype=np.float32)
    for i in range(0, len(bits), 2):
        pair = bits[i:i+2]
        tone_idx = pair[0] * 2 + pair[1]
        t = np.arange(samples_per_sym) / FS
        tone = np.sin(2 * np.pi * FREQS[tone_idx] * t)
        fade = int(0.005 * FS)
        if len(tone) > 2*fade:
            tone[:fade] *= np.linspace(0, 1, fade)
            tone[-fade:] *= np.linspace(1, 0, fade)
        signal = np.concatenate([signal, tone])
    return signal

# =====================================================================
# UNIFIED AUTOMATED ROUTING ENGINE
# =====================================================================

def execute_tx(args):
    """Unified Transmission Pipeline"""
    # Dynamic Code Routing Facade
    engines = {
        "hamming": HammingEngine,
        "selfdual": SDEngine,
        "qr": QREngine,
        "pg23": PG23Engine,
        "sts9": STS9Engine,
        "sts15": STS15Engine,
        "sqs16": SQS16Engine
    }
    engine = engines.get(args.ecc)
    if not engine:
        sys.stderr.write(f"[-] Invalid code scheme: {args.ecc}\n")
        sys.exit(1)
        
    v = args.q**2 + args.q + 1
    sys.stderr.write(f"[*] Initializing Acoustic Channel [Q={args.q}, Code={args.ecc.upper()}]\n")
    
    # --- Determine Payload Source ---
    if getattr(args, 'file', None):
        if not os.path.exists(args.file):
            sys.stderr.write(f"[-] Input file not found: {args.file}\n")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
            raw_message = "".join(filter(lambda x: 32 <= ord(x) <= 126, content))
            sys.stderr.write(f"[*] Sanitized input: {len(raw_message)} characters.\n")
    elif getattr(args, 'message', None):
        raw_message = args.message
    else:
        sys.stderr.write("[-] Error: You must provide either a text string or a -f/--file.\n")
        sys.exit(1)

    # 1. Calculate the CRC32 checksum
    crc_val = zlib.crc32(raw_message.encode('utf-8'))
    crc_hex = f"{crc_val:08x}"
    sys.stderr.write(f"[*] Payload CRC32 Checksum: {crc_hex}\n")
    
    # 2. Append checksum, then the stop byte
    message_with_crc = raw_message + crc_hex
    message_with_stop = message_with_crc + '\0'
    
    # 3. Encrypt and encode
    encrypted = xor_cipher(message_with_stop, SECRET_KEY)
    payload_bits = engine.string_to_bits(encrypted)
    
    # 4. size for header to support large text files
    header_width = 16 if args.extended else 8
    header_bits = [int(x) for x in bin(len(message_with_crc))[2:].zfill(header_width)]
    
    seq = get_singer_sequence(args.q)
    preamble_signal = np.concatenate([np.sin(2 * np.pi * (FREQS[0] if bit == 0 else FREQS[3]) * np.arange(int(T_S * FS)) / FS) for bit in seq])
    
    data_bits = header_bits + payload_bits
    sys.stderr.write(f"[*] DEBUG: Sending {len(message_with_crc)} bytes. Header width: {header_width}. Total bits: {len(data_bits)}\n")
    payload_signal = modulate_4ary(data_bits)
    
    silence_gap = np.zeros(int(0.25 * FS), dtype=np.float32)
    full_signal = np.concatenate([preamble_signal, silence_gap, payload_signal])
    
    wav.write(args.output, FS, (full_signal * 0.5 * 32767).astype(np.int16))
    sys.stderr.write(f"[+] Output written to {args.output} successfully.\n")

def execute_rx(args):
    """Unified Receiver Pipeline"""
    engines = {
        "hamming": HammingEngine,
        "selfdual": SDEngine,
        "qr": QREngine,
        "pg23": PG23Engine,
        "sts9": STS9Engine,
        "sts15": STS15Engine,
        "sqs16": SQS16Engine
    }
    engine = engines.get(args.ecc)
    
    # Explicit Hardware Routing
    if args.input == "MIC":
        sys.stderr.write(f"[*] Initializing Microphone Hook for {args.duration} seconds.\n")
        input("[>] Press ENTER, then immediately play the transmission audio...")
        sys.stderr.write("[*] Recording raw air gap data...\n")
        # Overwrite any old captured.wav file automatically
        os.system(f"arecord -d {args.duration} -r {FS} -f S16_LE captured.wav 2>/dev/null")
        target_file = "captured.wav"
    else:
        target_file = args.input
        
    if not os.path.exists(target_file):
        sys.stderr.write(f"[-] Input file not found: {target_file}\n")
        sys.exit(1)

    # Read from the securely routed target_file
    _, data = wav.read(target_file)
    if len(data.shape) > 1: data = data[:, 0]
    data = data.astype(np.float64)
    data -= np.mean(data)
    if np.max(np.abs(data)) > 0: data /= np.max(np.abs(data))

    seq = get_singer_sequence(args.q)
    template = np.concatenate([np.sin(2 * np.pi * (FREQS[0] if bit == 0 else FREQS[3]) * np.arange(int(T_S * FS)) / FS) for bit in seq])
    
    # Run cross correlation
    correlation = np.correlate(data, template, mode='valid')
    idx = np.argmax(np.abs(correlation))
    strength = np.abs(correlation[idx]) / np.sum(template**2)
    
    thresh = 0.06 if args.q == 7 else 0.08
    if strength < thresh:
        sys.stderr.write("[-] Frame Synchronization Lock Refused.\n")
        sys.exit(1)
        
    samples_per_bit = float(T_S * FS)
    silence_samples = int(0.25 * FS)
    payload_start = idx + (len(seq) * samples_per_bit) + silence_samples
    current_pos = payload_start
    
    # PI Loop Tuning Parameters
    alpha = 0.25  # Proportional gain: How aggressively to fix immediate phase drift
    beta = 0.002   # Integral gain: How quickly to learn and adjust to the hardware clock skew
    
    detected_bits = []
    
    # Dynamically read until we run out of audio samples
    while int(current_pos + samples_per_bit) < len(data):
        best_val, best_idx, best_nudge = -1, 0, 0
        
        # Scan slightly ahead and behind the expected center
        for nudge in range(-100, 101, 25):
            center = int(current_pos + (samples_per_bit / 2) + nudge)
            win = int(samples_per_bit / 8)
            chunk = data[center-win : center+win]
            
            if len(chunk) < win: continue
            
            mags = np.abs(np.fft.fft(chunk * np.blackman(len(chunk))))
            f_axis = np.fft.fftfreq(len(chunk), 1/FS)
            p_vals = [mags[np.argmin(np.abs(f_axis - f))] for f in FREQS]
            
            if max(p_vals) > best_val:
                best_val = max(p_vals)
                best_idx = p_vals.index(best_val)
                best_nudge = nudge
                
        detected_bits.extend([1 if best_idx >= 2 else 0, 1 if best_idx % 2 != 0 else 0])
        
        # --- The Second-Order PI Loop ---
        # 1. Proportional: Nudge the read head to the center of the current tone
        current_pos += samples_per_bit + (best_nudge * alpha)
        
        # 2. Integral: Permanently adjust the internal clock speed based on the drift trend
        samples_per_bit += (best_nudge * beta)
        
    sys.stderr.write(f"[*] DEBUG: Demodulated {len(detected_bits)} bits. "
                     f"Audio samples: {len(data)}. "
                     f"current_pos: {current_pos:.0f}\n")

    # Read 16 bits for the header
    header_width = 16 if args.extended else 8
    header_bits = detected_bits[:header_width]
    best_len = int("".join(map(str, header_bits)), 2)
    sys.stderr.write(f"[*] DEBUG: Header bits: {header_bits}. best_len = {best_len}\n")
    
    # Dynamic stride mapping allocation
    stride_map = {
        "hamming": 14, 
        "selfdual": 16, 
        "qr": 22, 
        "pg23": 14, 
        "sts9": 10, 
        "sts15": 16, 
        "sqs16": 16
    }
    stride = stride_map[args.ecc]
    
    # Calculate extraction sizes based on specific model architecture formulas
    if args.ecc == "sqs16":
        num_blocks = int(np.ceil(((best_len + 1) * 8) / 11))
    elif args.ecc == "sts15":
        num_blocks = int(np.ceil(((best_len + 1) * 8) / 11))
    elif args.ecc == "sts9":
        num_blocks = int(np.ceil(((best_len + 1) * 8) / 5))
    elif args.ecc == "pg23":
        num_blocks = int(np.ceil(((best_len + 1) * 8) / 9))
    elif args.ecc == "qr":
        num_blocks = best_len + 1
    else: # Hamming & Self-Dual
        num_blocks = best_len + 1
        
    payload_bits = detected_bits[header_width : header_width + (num_blocks * stride)]
    
    # 1. Get raw ciphertext string (must contain the \x00 byte from E^E)
    ciphertext_raw = engine.bits_to_string(payload_bits)
    
    # 2. Perform XOR on raw byte values to prevent encoding errors
    key_bytes = SECRET_KEY.encode('utf-8')
    ct_bytes = ciphertext_raw.encode('latin-1') # latin-1 preserves raw 0-255 values
    
    decrypted_bytes = bytearray()
    for i, b in enumerate(ct_bytes):
        decrypted_bytes.append(b ^ key_bytes[i % len(key_bytes)])
        
    # 3. Decode back to string AFTER decryption is complete
    recovered_full = decrypted_bytes.decode('utf-8', errors='ignore')
    
    # Strip trailing nulls
    clean_recovered = recovered_full.split('\0')[0]
    
    if len(clean_recovered) >= 8:
        # Separate message from the hex checksum
        recovered_msg = clean_recovered[:-8]
        recovered_crc_hex = clean_recovered[-8:]
        
        # Calculate expected checksum
        expected_crc_val = zlib.crc32(recovered_msg.encode('utf-8'))
        expected_crc_hex = f"{expected_crc_val:08x}"
        
        # Validate
        if recovered_crc_hex == expected_crc_hex:
            # Tell the user it worked and show the hash, but route it to stderr
            sys.stderr.write(f"[+] CRC32 Checksum Valid! ({recovered_crc_hex})\n")
            
            # Print ONLY the clean message to stdout so it can be piped to other programs
            print(recovered_msg)
        else:
            sys.stderr.write(f"[-] CRC32 Mismatch! Expected {expected_crc_hex}, got {recovered_crc_hex}\n")
            sys.stderr.write("[!] Output may be corrupted:\n")
            print(recovered_msg)
    else:
        sys.stderr.write("[-] Received payload too short to contain checksum.\n")
        print(f"Raw Output: {clean_recovered}")

# =====================================================================
# STANDARD UNIX CLI ENTRY INTERFACE
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acoustic Covert Channel System CLI Engine")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # Transmission argument configuration mapping
    tx_parser = subparsers.add_parser("tx", help="Transmit covert acoustic stream")
    tx_parser.add_argument("message", type=str, nargs="?", default=None, help="Payload data text string")
    tx_parser.add_argument("-f", "--file", type=str, help="Path to input .txt file")
    tx_parser.add_argument("-q", type=int, choices=[2, 3, 5, 7], default=5, help="Singer index plane size")
    tx_parser.add_argument("--extended", action="store_true", help="Use 16-bit header for files > 255 bytes")
    
    # ALL MODES REGISTERED HERE:
    tx_parser.add_argument("--ecc", type=str, 
                           choices=["hamming", "selfdual", "qr", "pg23", "sts9", "sts15", "sqs16"], 
                           default="sqs16", help="Geometric block code variant")
    
    tx_parser.add_argument("-o", "--output", type=str, default="transmit.wav", help="Target output wav path")
    tx_parser.set_defaults(func=execute_tx)

    # Reception argument configuration mapping
    rx_parser = subparsers.add_parser("rx", help="Receive and decode air-gap stream")
    rx_parser.add_argument("-i", "--input", type=str, default="MIC", help="Source audio wave track or 'MIC' for live recording")
    rx_parser.add_argument("-q", type=int, choices=[2, 3, 5, 7], default=5, help="Expected Preamble index")
    rx_parser.add_argument("--extended", action="store_true", help="Expect 16-bit header")
    
    # ALL MODES REGISTERED HERE:
    rx_parser.add_argument("--ecc", type=str, 
                           choices=["hamming", "selfdual", "qr", "pg23", "sts9", "sts15", "sqs16"], 
                           default="sqs16", help="Expected decoding space template")
    
    rx_parser.add_argument("-d", "--duration", type=int, default=25, help="Microphone recording duration")
    rx_parser.set_defaults(func=execute_rx)

    args = parser.parse_args()
    if args.mode == "tx": execute_tx(args)
    elif args.mode == "rx": execute_rx(args)