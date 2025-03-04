#! /usr/bin/env python

import os
import re
from itertools import count

from copy import deepcopy


class Formats:

    MAGIC_NUMBER = b'\x02\x01\x04\x03\x06\x05\x08\x07'

    PROFILE_CFG_FORMAT = {
        'sensorStop': None,
        'flushCfg': None,
        'dfeDataOutputMode': {'modeType': int},
        'channelCfg': {
            'rxAntBitmap': int,
            'txAntBitmap': int,
            'cascading': int},
        'adcCfg': {
            'numADCBits': int,
            'adcOutputFmt': int},
        'adcbufCfg': {
            'subFrameIdx': int,
            'adcOutputFmt': int,
            'SampleSwap': int,
            'chanInterleave': int,
            'chirpThreshold': int},
        'profileCfg': {
            'profileId': int,
            'startFreq': float,
            'idleTime': float,
            'adcStartTime': float,
            'rampEndTime': float,
            'txOutPower': int,
            'txPhaseShifter': int,
            'freqSlopeConst': float,
            'txStartTime': float,
            'numAdcSamples': int,
            'digOutSampleRate': int,
            'hpfCornerFreq1': int,
            'hpfCornerFreq2': int,
            'rxGain': int},
        'chirpCfg': {
            'chirpStartIdx': int,
            'chirpEndIdx': int,
            'profileId': int,
            'startFreqVar': float,
            'freqSlopeVar': float,
            'idleTimeVar': float,
            'adcStartTimeVar': float,
            'txAntBitmask': int},
        'frameCfg': {
            'chirpStartIdx': int,
            'chirpEndIdx': int,
            'nLoops': int,
            'nFrames': int,
            'framePeriod': float,
            'triggerSelect': int,
            'triggerDelay': float},
        'lowPower': {
            'subFrameIdx': int,
            'adcMode': int},
        'guiMonitor': {
            'subFrameIdx': int,
            'detectedObjects': int,
            'logMagnitudeRange': int,
            'noiseProfile': int,
            'rangeAzimuthHeatMap': int,
            'rangeDopplerHeatMap': int,
            'statsInfo': int},
        'cfarCfg': {
            'subFrameIdx': int,
            'procDirection': int,
            'averageMode': int,
            'winLen': int,
            'guardLen': int,
            'noiseDiv': int,
            'cyclicMode': int,
            'thresholdScale': int},
        'peakGrouping': {
            'subFrameIdx': int,
            'groupingMode': int,
            'rangeDimEn': int,
            'dopplerDimEn': int,
            'startRangeIdx': int,
            'endRangeIdx': int},
        'multiObjBeamForming': {
            'subFrameIdx': int,
            'enabled': int,
            'threshold': float},
        'clutterRemoval': {
            'subFrameIdx': int,
            'enabled': int},
        'calibDcRangeSig': {
            'subFrameIdx': int,
            'enabled': int,
            'negativeBinIdx': int,
            'positiveBinIdx': int,
            'numAvgFrames': int},
        'extendedMaxVelocity': {
            'subFrameIdx': int,
            'enabled': int},
        'bpmCfg': {
            'subFrameIdx': int,
            'isEnabled': int,
            'chirp0Idx': int,
            'chirp1Idx': int},
        'lvdsStreamCfg': {
            'subFrameIdx': int,
            'isHeaderEnabled ': int,
            'dataFmt': int,
            'isSwEnabled': int},
        'nearFieldCfg': {
            'subFrameIdx': int,
            'enabled': int,
            'startRangeIndex': int,
            'endRangeIndex': int},
        'compRangeBiasAndRxChanPhase': {
            'rangeBias': float,
            'Re00': float,
            'Im00': float,
            'Re01': float,
            'Im01': float,
            'Re02': float,
            'Im02': float,
            'Re03': float,
            'Im03': float,
            'Re10': float,
            'Im10': float,
            'Re11': float,
            'Im11': float,
            'Re12': float,
            'Im12': float,
            'Re13': float,
            'Im13': float},
        'measureRangeBiasAndRxChanPhase': {
            'enabled': int,
            'targetDistance': float,
            'searchWin': float},
        'CQRxSatMonitor': {
            'profileIndx': int,
            'satMonSel': int,
            'primarySliceDuration': int,
            'numSlices': int,
            'rxChannelMask': int},
        'CQSigImgMonitor': {
            'profileIndx': int,
            'numSlices': int,
            'timeSliceNumSamples': int},
        'analogMonitor': {
            'rxSatMonEn ': int,
            'sigImgMonEn ': int}
    }

    HEADER_FORMAT = {
        'name': 'header',
        'values': {
            'magic': '8s',
            'version': '4s',
            'packet_len': 'I',
            'platform': '4s',
            'frame_num': 'I',
            'time_cpu_cyc': 'I',
            'num_det_obj': 'I',
            'num_tlvs': 'I',
            'unknown': 'I'}
    }

    TLVS_FORMAT = {
        1: {'name': 'detectedPoints',
            'values': {
                'descriptor': {
                    'num_det_obj': 'H',
                    'xyz_q_format': 'H'},
                'objs': ['descriptor.num_det_obj', {
                    'range_idx': 'H',
                    'doppler_idx': 'H',
                    'peak_value': 'H',
                    'x_coord': 'H',
                    'y_coord': 'H',
                    'z_coord': 'H'}]}},
        2: {'name': 'rangeProfile',
            'values': '%sf'},
        3: {'name': 'noiseProfile',
            'values': '%sf'},
        4: {'name': 'rangeAzimuthHeatMap',
            'values': '%sf'},
        5: {'name': 'rangeDoplerHeatMap',
            'values': '%sf'},
        6: {'name': 'stats',
            'values': {
                'Inter-frame Processing Time': 'I',
                'Transmit Output Time': 'I',
                'Inter-frame Processing Margin': 'I',
                'Inter-chirp Processing Margin': 'I',
                'Active Frame CPU Load': 'I',
                'InterframeCPU Load': 'I'}}
    }

    def __init__(self, config):
        self.config = self.parse_config(config)

        self.header = self.config_header()
        self.tlvs = self.config_tlvs()

    def parse_config(self, config_file):
        format = self.PROFILE_CFG_FORMAT

        with open(config_file, 'r') as f:
            lines = f.readlines()

        # Initialize config
        config = {}
        for line in lines:
            line = line.strip()

            # Skip comment lines and blank lines
            if re.match('^\s*%|^\s*$', line):
                continue

            words = line.split()
            cmd = words[0]
            if format.get(cmd) is not None:
                config[cmd] = {}
                for i, param in enumerate(format[cmd]):
                    config[cmd][param] = format[cmd][param](words[i+1])

        return config

    def config_header(self):
        return self.HEADER_FORMAT

    def config_tlvs(self):
        format = deepcopy(self.TLVS_FORMAT)

        adc_samples = self.config['profileCfg']['numAdcSamples']

        #  RangeBins: number of ADC samples rounded up to the nearest power of 2
        for factor in count():
            res = 2**factor
            if res >= adc_samples:
                if (res - adc_samples) < (adc_samples - res/2):
                    adc_samples = res
                else:
                    adc_samples = res//2
                break

        #  Size: RangeBins
        format[2]['values'] %= str(adc_samples)
        #  Size: RangeBins
        format[3]['values'] %= str(adc_samples)

        #  Size: RangeBins * num_virtual_antennas
        num_rx = bin(self.config['channelCfg']['rxAntBitmap']).count('1')
        num_tx = bin(self.config['channelCfg']['txAntBitmap']).count('1')
        format[4]['values'] %= str(adc_samples*num_rx*num_tx)

        #  Size: RangeBins * DopplerBins
        chirps_per_frame = (self.config['frameCfg']['chirpEndIdx'] -
                            self.config['frameCfg']['chirpStartIdx'])
        format[5]['values'] %= str(adc_samples*chirps_per_frame//num_tx)

        return format


class GESTURE:
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    CW = 4
    CCW = 5
    Z = 6
    S = 7
    X = 8

    @staticmethod
    def __is_gesture(attr):
        return (not attr.startswith("__") and isinstance(getattr(GESTURE, attr), int))

    @staticmethod
    def to_str(gesture):
        for attr in dir(GESTURE):
            if GESTURE.__is_gesture(attr) and getattr(GESTURE, attr) == gesture:
                return attr.lower()

    @staticmethod
    def from_str(str):
        for attr in dir(GESTURE):
            if str.upper() == attr and GESTURE.__is_gesture(attr):
                return getattr(GESTURE, attr)

    @staticmethod
    def get_dir(gesture):
        if type(gesture) == str:
            gesture = GESTURE.from_str(gesture)

        if gesture in GESTURE.get_all_gestures():
            return os.path.join(os.path.dirname(__file__), GESTURE.to_str(gesture))

    @staticmethod
    def get_all_gestures():
        return sorted([getattr(GESTURE, attr) for attr in dir(GESTURE)
                        if not attr.startswith("__")
                            and isinstance(getattr(GESTURE, attr), int)])

    @staticmethod
    def num_of_gestures():
        return len(GESTURE.get_all_gestures)
