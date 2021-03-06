'''
PartsGenie (c) University of Manchester 2017

PartsGenie is licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>.

@author:  neilswainston
'''
# pylint: disable=no-self-use
import collections
import copy
from itertools import product
import math

from parts_genie import rbs_calculator as rbs_calc
from synbiochem.optimisation.sim_ann import SimulatedAnnealer
from synbiochem.utils import dna_utils, seq_utils


class PartsSolution(object):
    '''Solution for RBS optimisation.'''

    def __init__(self, dna, organism, filters):
        self.__dna = dna_utils.get_dna(dna)
        self.__dna['typ'] = dna_utils.SO_PART
        self.__dna['parameters']['Type'] = 'PART'
        self.__organism = organism
        self.__filters = filters
        self.__filters['restr_enzs'] = self.__filters.get('restr_enzs', [])

        self.__calc = rbs_calc.RbsCalculator(organism['r_rna']) \
            if self.__organism else None

        self.__cod_opt = seq_utils.CodonOptimiser(organism['taxonomy_id']) \
            if self.__organism else None

        self.__dna_new = None

    def init(self):
        '''Initialisation method for longer initiation tasks.'''
        self.__calc_num_fixed()
        self.__init_seqs()
        self.__update(self.__dna)

        self.__dna_new = copy.deepcopy(self.__dna)

    def get_query(self):
        '''Return query.'''
        return {'dna': self.__dna,
                'organism': self.__organism,
                'filters': self.__filters}

    def get_values(self):
        '''Return update of in-progress solution.'''
        keys = ['id', 'name', 'value', 'min', 'max',
                'target_min', 'target_max']
        params = self.__dna['temp_params']

        if params:
            return [dict(zip(keys, ('mean_cai',
                                    'CAI',
                                    params['mean_cai'],
                                    0, 1, 0.9, 1))),
                    dict(zip(keys, ('mean_tir',
                                    'TIR',
                                    params['mean_tir_errs'],
                                    0, 1, 0, 0.05))),
                    dict(zip(keys, ('num_invalid_seqs',
                                    'Invalid seqs',
                                    params['num_inv_seq'],
                                    0, 10, 0, 0.5))),
                    dict(zip(keys, ('num_rogue_rbs',
                                    'Rogue RBSs',
                                    params['num_rogue_rbs'],
                                    0, 10, 0, 0.5))),
                    dict(zip(keys, ('global_gc',
                                    'Global GC',
                                    self.__dna['parameters']['Global GC'],
                                    0, 1, 0.25, 0.65))),
                    dict(zip(keys, ('local_gc',
                                    'Local GC',
                                    self.__dna['temp_params']['Local GC'],
                                    0, 10, 0, 0.5))),
                    dict(zip(keys, ('repeats',
                                    'Repeats',
                                    self.__dna['temp_params']['num_repeats'],
                                    0, 10, 0, 0.5)))]
        # else:
        return []

    def get_result(self):
        '''Return result of solution.'''
        dnas = dna_utils.expand(self.__dna)

        import json
        print json.dumps(dnas, indent=2)

        return dnas

    def get_energy(self, dna=None):
        '''Gets the (simulated annealing) energy.'''
        return float('inf') if dna is None else dna['temp_params']['energy']

    def mutate(self):
        '''Mutates and scores whole design.'''
        for feature in self.__dna_new['features']:
            if feature['typ'] == dna_utils.SO_CDS:
                for cds in feature['options']:
                    if not cds['temp_params']['fixed']:
                        mutation_rate = 5.0 / len(cds['temp_params']['aa_seq'])
                        cds.set_seq(self.__cod_opt.mutate(
                            cds['temp_params']['aa_seq'],
                            cds['seq'],
                            mutation_rate))
            elif not feature['temp_params']['fixed']:
                feature.set_seq(seq_utils.mutate_seq(feature['seq'],
                                                     mutations=3))

        return self.__update(self.__dna_new)

    def accept(self):
        '''Accept potential update.'''
        self.__dna = copy.deepcopy(self.__dna_new)

    def reject(self):
        '''Reject potential update.'''
        self.__dna_new = copy.deepcopy(self.__dna)

    def __calc_num_fixed(self, flank=16):
        '''Calculate number of anomolies in fixed sequences.'''
        fixed_seqs = [feat['seq']
                      for feat in self.__dna['features']
                      if feat['temp_params'].get('fixed', False)]

        flanked_fixed_seqs = ['N' * flank + seq + 'N' * flank
                              for seq in fixed_seqs]

        self.__calc_num_inv_seq_fixed(flanked_fixed_seqs)
        self.__calc_num_local_gc_fixed(fixed_seqs)
        self.__calc_num_repeats_fixed(fixed_seqs)

    def __calc_num_inv_seq_fixed(self, fixed_seqs):
        '''Calculate number of invalid sequences in fixed sequences.'''
        self.__dna['temp_params']['num_inv_seq_fixed'] = \
            sum([len(seq_utils.find_invalid(seq,
                                            self.__filters['max_repeats'],
                                            self.__filters['restr_enzs']))
                 for seq in fixed_seqs])

    def __calc_num_local_gc_fixed(self, fixed_seqs):
        '''Calculate number of invalid sequences in fixed sequences.'''
        self.__dna['temp_params']['num_local_gc_fixed'] = \
            _get_local_gc(fixed_seqs)

    def __calc_num_repeats_fixed(self, fixed_seqs):
        '''Calculate number of invalid sequences in fixed sequences.'''
        self.__dna['temp_params']['num_repeats_fixed'] = \
            _get_repeats(fixed_seqs)

    def __init_seqs(self):
        '''Returns sequences from protein ids, which may be either Uniprot ids,
        or a protein sequence itself.'''
        for idx, feature in enumerate(self.__dna['features']):
            if feature['typ'] == dna_utils.SO_CDS:
                for cds in feature['options']:
                    cds['temp_params']['aa_seq'] = \
                        ''.join(cds['temp_params']['aa_seq'].upper().split())

                    if cds['temp_params']['aa_seq'][-1] != '*':
                        cds['temp_params']['aa_seq'] += '*'

                    cds['links'].append(
                        'http://identifiers.org/taxonomy/' +
                        self.__organism['taxonomy_id'])

                    cds.set_seq(self.__cod_opt.get_codon_optim_seq(
                        cds['temp_params']['aa_seq'],
                        self.__filters.get('excl_codons', None),
                        self.__filters['max_repeats'],
                        self.__filters['restr_enzs'],
                        tolerant=False))

            elif feature['typ'] == dna_utils.SO_RBS:
                # Randomly choose an RBS that is a decent starting point,
                # using the first CDS as the upstream sequence:
                feature.set_seq(self.__calc.get_initial_rbs(
                    feature['end'],
                    self.__dna['features'][idx + 1]['options'][0]['seq'],
                    feature['parameters']['TIR target']))

            elif feature['typ'] == dna_utils.SO_ASS_COMP:
                # Generate bridging oligo site of desired melting temp:
                if not feature['seq']:
                    seq, melt_temp = seq_utils.get_rand_seq_by_melt_temp(
                        feature['parameters']['Tm target'],
                        self.__filters['max_repeats'],
                        self.__filters['restr_enzs'])

                    feature.set_seq(seq)
                else:
                    melt_temp = seq_utils.get_melting_temp(feature['seq'])

                feature['parameters']['Tm'] = melt_temp

            elif feature['typ'] == dna_utils.SO_RANDOM:
                # Randomly choose a sequence:
                seq = seq_utils.get_random_dna(feature.pop('end'),
                                               self.__filters['max_repeats'],
                                               self.__filters['restr_enzs'])
                feature.set_seq(seq)
            else:
                feature['seq'] = ''.join(feature['seq'].upper().split())

    def __update(self, dna):
        '''Calculates (simulated annealing) energies for given RBS.'''
        cais = []
        tir_errs = []
        num_rogue_rbs = 0

        for idx, feature in enumerate(dna['features']):
            if feature['typ'] == dna_utils.SO_RBS:
                for cds in dna['features'][idx + 1]['options']:
                    tir_err, rogue_rbs = self.__calc_tirs(feature, cds)
                    tir_errs.append(tir_err)
                    num_rogue_rbs += len(rogue_rbs)

            elif feature['typ'] == dna_utils.SO_CDS:
                for cds in feature['options']:
                    cai = self.__cod_opt.get_cai(cds['seq'])
                    cds['parameters']['CAI'] = cai
                    cais.append(cai)

        dna['temp_params']['mean_cai'] = _mean(cais)
        dna['temp_params']['mean_tir_errs'] = _mean(tir_errs) \
            if tir_errs else 0
        dna['temp_params']['num_rogue_rbs'] = num_rogue_rbs

        # Get number of invalid seqs:
        all_seqs = _get_all_seqs(dna)

        dna['temp_params']['num_inv_seq'] = \
            sum([len(seq_utils.find_invalid(seq,
                                            self.__filters['max_repeats'],
                                            self.__filters['restr_enzs']))
                 for seq in all_seqs]) - \
            dna['temp_params']['num_inv_seq_fixed']

        # Calculate global GC content:
        dna['parameters']['Global GC'] = \
            _mean([_get_gc(seq) for seq in all_seqs])

        dna['temp_params']['Local GC'] = _get_local_gc(all_seqs) - \
            self.__dna['temp_params']['num_local_gc_fixed']

        dna['temp_params']['num_repeats'] = _get_repeats(all_seqs) - \
            self.__dna['temp_params']['num_repeats_fixed']

        dna['temp_params']['energy'] = dna['temp_params']['mean_tir_errs'] + \
            dna['temp_params']['num_inv_seq'] + \
            dna['temp_params']['num_rogue_rbs'] + \
            _get_delta_range(0.25, 0.65, dna['parameters']['Global GC']) + \
            dna['temp_params']['Local GC'] + \
            dna['temp_params']['num_repeats']

        return self.get_energy(dna)

    def __calc_tirs(self, rbs, cds):
        '''Performs TIR calculations.'''
        tir_vals = self.__calc.calc_dgs(rbs['seq'] + cds['seq'])

        cds['temp_params']['tir_vals'] = tir_vals

        # Get TIR:
        tir = tir_vals[rbs['end']][1]
        cds['parameters']['TIR'] = tir
        target = rbs['parameters']['TIR target']

        try:
            tir_err = 1 - math.log(target - abs(target - tir), target)
        except ValueError:
            # If tir is -ve, set tir_err to be a large number:
            tir_err = 2.0 ** 32

        # Get rogue RBS sites:
        cutoff = 0.1
        rogue_rbs = [(pos, terms)
                     for pos, terms in tir_vals.iteritems()
                     if pos != rbs['end'] and terms[1] >
                     rbs['parameters']['TIR target'] * cutoff]

        return tir_err, rogue_rbs

    def __repr__(self):
        # return '%r' % (self.__dict__)
        tirs = []
        cais = []

        for feature in self.__dna['features']:
            if feature['typ'] == dna_utils.SO_CDS:
                for cds in feature['options']:
                    tirs.append(cds['parameters'].get('TIR', None))
                    cais.append(cds['parameters']['CAI'])

        return '\t'.join([str(tirs),
                          str(cais),
                          str(self.__dna['parameters']['Global GC']),
                          str(self.__dna['temp_params']['num_inv_seq']),
                          str(self.__dna['temp_params']['num_rogue_rbs']),
                          str(self.__dna['temp_params']['Local GC']),
                          str(self.__dna['temp_params']['num_repeats'])])

    def __print__(self):
        return self.__repr__


class PartsThread(SimulatedAnnealer):
    '''Wraps a PartsGenie job into a thread.'''

    def __init__(self, query, idx, verbose=True):
        solution = PartsSolution(query['designs'][idx],
                                 query.get('organism', None),
                                 query['filters'])

        SimulatedAnnealer.__init__(self, solution, verbose=verbose)


def _mean(lst):
    '''Gets mean of list.'''
    return float(sum(lst)) / len(lst) if lst else 0.0


def _get_delta_range(min_val, max_val, val):
    '''Gets delta of val from min_val, max_val range.'''
    if val < min_val:
        return min_val - val
    if val > max_val:
        return val - max_val

    return 0


def _get_gc(seq):
    '''Get GC content.'''
    return (seq.count('G') + seq.count('C')) / float(len(seq))


def _get_local_gc(seqs, window_size=50, min_val=0.15, max_val=0.8):
    '''Get local GC score.'''
    local_gc = 0

    for seq in seqs:
        for idx in range(len(seq) - window_size + 1):
            if _get_delta_range(min_val, max_val,
                                _get_gc(seq[idx:idx + window_size])):
                local_gc += 1

    return local_gc


def _get_repeats(seqs, window_size=25):
    '''Get local GC score.'''
    repeats = 0

    for seq in seqs:
        windows = [seq[idx:idx + window_size]
                   for idx in range(len(seq) - window_size + 1)]
        counter = collections.Counter(windows)
        repeats += sum(i for i in counter.values() if i > 1)

    return repeats


def _get_all_seqs(dna):
    '''Return all sequences.'''
    all_seqs = ['']

    for feature in dna['features']:
        if feature['typ'] == dna_utils.SO_CDS:
            options = [option['seq'] for option in feature['options']]
            all_seqs = [''.join(term) for term in product(all_seqs, options)]
        else:
            for idx, seq in enumerate(all_seqs):
                all_seqs[idx] = seq + feature['seq']

    return all_seqs
