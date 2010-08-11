# Natural Language Toolkit: Interface to Boxer
# <http://svn.ask.it.usyd.edu.au/trac/candc/wiki/boxer>
#
# Author: Dan Garrette <dhgarrette@gmail.com>
#
# Copyright (C) 2001-2010 NLTK Project
# URL: <http://www.nltk.org/>
# For license information, see LICENSE.TXT

from __future__ import with_statement
import os
import subprocess
from optparse import OptionParser
import tempfile

import nltk
from nltk.sem.logic import *
from nltk.sem.drt import *

"""
An interface to Boxer.

Usage:
  Set the environment variable CANDCHOME to the bin directory of your CandC installation.
  The models directory should be in the CandC root directory.
  For example:
     /path/to/candc/
        bin/
            candc
            boxer
        models/
            boxer/
"""

class Boxer(object):
    """
    This class is used to parse a sentence using Boxer into an NLTK DRS 
    object.  The BoxerDrsParser class is used for the actual conversion.
    """

    def __init__(self):
        self._boxer_bin = None
        self._candc_bin = None
        self._candc_models_path = None
    
    def interpret(self, input, occur_index=False, discourse_id=None, verbose=False):
        """
        Use Boxer to give a first order representation.
        
        @param input: C{str} Input sentence to parse
        @param occur_index: C{boolean} Should predicates be occurrence indexed?
        @param discourse_id: C{str} An identifier to be inserted to each occurrence-indexed predicate.
        @return: C{drt.AbstractDrs}
        """
        discourse_ids = [discourse_id] if discourse_id is not None else None 
        return self.batch_interpret_multisentence([[input]], occur_index, discourse_ids, verbose)[0]
    
    def interpret_multisentence(self, input, occur_index=False, discourse_id=None, verbose=False):
        """
        Use Boxer to give a first order representation.
        
        @param input: C{list} of C{str} Input sentences to parse as a single discourse
        @param occur_index: C{boolean} Should predicates be occurrence indexed?
        @param discourse_id: C{str} An identifier to be inserted to each occurrence-indexed predicate.
        @return: C{drt.AbstractDrs}
        """
        discourse_ids = [discourse_id] if discourse_id is not None else None
        return self.batch_interpret_multisentence([input], occur_index, discourse_ids, verbose)[0]
        
    def batch_interpret(self, inputs, occur_index=False, discourse_ids=None, verbose=False):
        """
        Use Boxer to give a first order representation.
        
        @param inputs: C{list} of C{str} Input sentences to parse as individual discourses
        @param occur_index: C{boolean} Should predicates be occurrence indexed?
        @param discourse_ids: C{list} of C{str} Identifiers to be inserted to each occurrence-indexed predicate.
        @return: C{list} of C{drt.AbstractDrs}
        """
        return self.batch_interpret_multisentence([[input] for input in inputs], occur_index, discourse_ids, verbose)

    def batch_interpret_multisentence(self, inputs, occur_index=False, discourse_ids=None, verbose=False):
        """
        Use Boxer to give a first order representation.
        
        @param inputs: C{list} of C{list} of C{str} Input discourses to parse
        @param occur_index: C{boolean} Should predicates be occurrence indexed?
        @param discourse_ids: C{list} of C{str} Identifiers to be inserted to each occurrence-indexed predicate.
        @return: C{drt.AbstractDrs}
        """
        _, temp_filename = tempfile.mkstemp(prefix='boxer-', suffix='.in', text=True)

        if discourse_ids is not None:
            assert len(inputs) == len(discourse_ids)
            assert all(id is not None for id in discourse_ids)
            use_disc_id = True
        else:
            discourse_ids = map(str, xrange(len(inputs)))
            use_disc_id = False
            
        candc_out = self._call_candc(inputs, discourse_ids, temp_filename, verbose=verbose)
        boxer_out = self._call_boxer(temp_filename, verbose=verbose)

        os.remove(temp_filename)

#        if 'ERROR: input file contains no ccg/2 terms.' in boxer_out:
#            raise UnparseableInputException('Could not parse with candc: "%s"' % input_str)

        drs_dict = self._parse_to_drs_dict(boxer_out, occur_index, use_disc_id)
        return [drs_dict.get(id, None) for id in discourse_ids]
        
    def _call_candc(self, inputs, discourse_ids, filename, verbose=False):
        """
        Call the C{candc} binary with the given input.

        @param inputs: C{list} of C{list} of C{str} Input discourses to parse
        @param discourse_ids: C{list} of C{str} Identifiers to be inserted to each occurrence-indexed predicate.
        @param filename: C{str} A filename for the output file
        @return: stdout
        """
        if self._candc_bin is None:
            self._candc_bin = self._find_binary('candc', verbose)
        if self._candc_models_path is None:
            self._candc_models_path = os.path.normpath(os.path.join(self._candc_bin[:-5], '../models'))
        args = ['--models', os.path.join(self._candc_models_path, 'boxer'), 
                '--output', filename]

        return self._call('\n'.join(sum((["<META>'%s'" % id] + d for d,id in zip(inputs,discourse_ids)), [])), self._candc_bin, args, verbose)

    def _call_boxer(self, filename, verbose=False):
        """
        Call the C{boxer} binary with the given input.
    
        @param filename: C{str} A filename for the input file
        @return: stdout
        """
        if self._boxer_bin is None:
            self._boxer_bin = self._find_binary('boxer', verbose)
        args = ['--box', 'false', 
                '--semantics', 'drs',
                '--format', 'prolog', 
                '--flat', 'false',
                '--resolve', 'true',
                '--elimeq', 'true',
                '--input', filename]

        return self._call(None, self._boxer_bin, args, verbose)

    def _find_binary(self, name, verbose=False):
        return nltk.internals.find_binary(name, 
            env_vars=['CANDCHOME'],
            url='http://svn.ask.it.usyd.edu.au/trac/candc/',
            binary_names=[name, name + '.exe'],
            verbose=verbose)
    
    def _call(self, input_str, binary, args=[], verbose=False):
        """
        Call the binary with the given input.
    
        @param input_str: A string whose contents are used as stdin.
        @param binary: The location of the binary to call
        @param args: A list of command-line arguments.
        @return: stdout
        """
        if verbose:
            print 'Calling:', binary
            print 'Args:', args
            print 'Input:', input_str
            print 'Command:', binary + ' ' + ' '.join(args)
        
        # Call via a subprocess
        if input_str is None:
            cmd = [binary] + args
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            cmd = 'echo "%s" | %s %s' % (input_str, binary, ' '.join(args))
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = p.communicate()
        
        if verbose:
            print 'Return code:', p.returncode
            if stdout: print 'stdout:\n', stdout, '\n'
            if stderr: print 'stderr:\n', stderr, '\n'
        if p.returncode != 0:
            raise Exception('ERROR CALLING: %s %s\nReturncode: %d\n%s' % (binary, ' '.join(args), p.returncode, stderr))
            
        return stdout

    def _parse_to_drs_dict(self, boxer_out, occur_index, use_disc_id):
        lines = boxer_out.split('\n')
        drs_dict = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('id('):
                comma_idx = line.index(',')
                discourse_id = line[3:comma_idx]
                if discourse_id[0] == "'" and discourse_id[-1] == "'":
                    discourse_id = discourse_id[1:-1]
                drs_id = line[comma_idx+1:line.index(')')]
                line = lines[i+4]
                assert line.startswith('sem(%s,' % drs_id)
                line = lines[i+8]
                assert line.endswith(').')
                drs_input = line[:-2].strip()
                drs = BoxerDrsParser(occur_index, discourse_id if use_disc_id else None).parse(drs_input).simplify()
                drs = self._clean_drs(drs)
                drs_dict[discourse_id] = drs
                i += 8
            i += 1
        return drs_dict

    def _clean_drs(self, drs):
        #Remove compound nouns
        drs = self._nn(drs)
        return drs

    def _nn(self, drs):
        if isinstance(drs, DRS):
            return DRS(drs.refs, map(self._nn, drs.conds))
        elif isinstance(drs, DrtNegatedExpression):
            return DrtNegatedExpression(self._nn(drs.term))
        elif isinstance(drs, DrtLambdaExpression):
            return DrtLambdaExpression(drs.variable, self._nn(drs.term))
        elif isinstance(drs, BinaryExpression):
            return drs.__class__(self._nn(drs.first), self._nn(drs.second))
        elif isinstance(drs, DrtApplicationExpression):
            func, args = drs.uncurry()
            if func.variable.name == 'r_nn_2':
                assert len(args) == 2
                return DrtEqualityExpression(*args)
            else:
                accum = self._nn(func)
                for arg in args:
                    accum = accum(self._nn(arg))
                return accum
        return drs


class BoxerDrsParser(DrtParser):
    def __init__(self, occur_index=False, discourse_id=None):
        """
        This class is used to parse the Prolog DRS output from Boxer into an
        NLTK DRS object.  Predicates are parsed into the form:

        <pos>_<word>[_<discourse id>][_s<sentence index>_w<word index>]_arity

        So, the binary predicate representing the word 'see', which is a verb,
        appearing as the fourth word of the third sentence of discourse 't' 
        would be:

        v_see_t_s3_w4_2

        Note that sentence id and occurrence indexing are optional and controlled
        by parameters.

        @param occur_index: C{boolean} Should predicates be occurrence indexed?
        @param discourse_id: C{str} An identifier to be inserted to each 
            occurrence-indexed predicate.
        """
        DrtParser.__init__(self)
        self.occur_index = occur_index
        self.discourse_id = discourse_id
        self.quote_chars = [("'", "'", "\\", False)]
    
    def get_all_symbols(self):
        return ['(', ')', ',', '[', ']',':']

    def handle(self, tok, context):
        return self.handle_drs(tok)
    
    def attempt_adjuncts(self, expression, context):
        return expression

    def parse_condition(self, indices):
        """
        Parse a DRS condition

        @return: C{list} of C{AbstractDrs}
        """
        tok = self.token()
        accum = self.handle_condition(tok, indices)
        if accum is None:
            raise UnexpectedTokenException(tok)
        return accum

    def handle_drs(self, tok):
        if tok == 'drs':
            return self.parse_drs()
        elif tok == 'merge':
            return self._make_binary_expression(ConcatenationDRS)
        elif tok == 'smerge':
            return self._make_binary_expression(ConcatenationDRS)

    def handle_condition(self, tok, indices):
        """
        Handle a DRS condition

        @param indices: C{list} of C{int}
        @return: C{list} of C{AbstractDrs}
        """
        if tok == 'not':
            self.assertToken(self.token(), '(')
            e = self.parse_Expression(None)
            self.assertToken(self.token(), ')')
            return [DrtNegatedExpression(e)]

        elif tok == 'or':
            return [self._make_binary_expression(DrtOrExpression)]
        elif tok == 'imp':
            return [self._make_binary_expression(DrtImpExpression)]
        elif tok == 'eq':
            return [self._handle_eq(indices)]
        elif tok == 'prop':
            return [self._handle_prop(indices)]

        elif tok == 'pred':
            return [self._handle_pred(indices)]
        elif tok == 'named':
            return [self._handle_named(indices)]
        elif tok == 'rel':
            return [self._handle_rel(indices)]
        elif tok == 'timex':
            return self._handle_timex(indices)
        elif tok == 'card':
            return [self._handle_card(indices)]

        elif tok == 'whq':
            return [self._handle_whq(indices)]

    def _handle_pred(self, indices):
        #pred(_G3943, dog, n, 0)
        self.assertToken(self.token(), '(')
        arg = self.token()
        self.assertToken(self.token(), ',')
        f_name = self._format_pred_name(self.token())
        self.assertToken(self.token(), ',')
        f_pos = self.token()
        self.assertToken(self.token(), ',')
        f_sense = self.token()
        self.assertToken(self.token(), ')')
        f_pred = self._make_pred(f_pos, f_name, indices, 1)
        return self._make_atom(f_pred, arg)

    def _format_pred_name(self, name):
        out = ''
        for c in name:
            #if c not in '-\'"()[]/\\:;.,?+!`':
            if 'A' <= c <= 'Z' or \
               'a' <= c <= 'z' or \
               '0' <= c <= '9' or \
               c == '_':
                out += c
        return out

    def _handle_named(self, indices):
        #named(x0, john, per, 0)
        self.assertToken(self.token(), '(')
        arg = self.token()
        self.assertToken(self.token(), ',')
        f_name = self._format_pred_name(self.token())
        self.assertToken(self.token(), ',')
        f_pos = self.token()
        self.assertToken(self.token(), ',')
        f_sense = self.token()
        self.assertToken(self.token(), ')')
        f_pred = 'n_%s_%s' % (f_name, 1)
        return self._make_atom(f_pred, arg)

    def _handle_rel(self, indices):
        #rel(_G3993, _G3943, agent, 0)
        self.assertToken(self.token(), '(')
        arg1 = self.token()
        self.assertToken(self.token(), ',')
        arg2 = self.token()
        self.assertToken(self.token(), ',')
        f_name = self._format_pred_name(self.token())
        self.assertToken(self.token(), ',')
        f_sense = self.token()
        self.assertToken(self.token(), ')')
        f_pred = 'r_%s_%s' % (f_name, 2)
        return self._make_atom(f_pred, arg1, arg2)

    def _handle_timex(self, indices):
        #timex(_G18322, date([]: +, []:'XXXX', [1004]:'04', []:'XX'))
        self.assertToken(self.token(), '(')
        arg = self.token()
        self.assertToken(self.token(), ',')
        new_conds = self._handle_time_expression(arg)
        self.assertToken(self.token(), ')')
        return new_conds

    def _handle_time_expression(self, arg):
        #date([]: +, []:'XXXX', [1004]:'04', []:'XX')
        tok = self.token()
        self.assertToken(self.token(), '(')
        if tok == 'date':
            conds = self._handle_date(arg)
        elif tok == 'time':
            conds = self._handle_time(arg)
        else:
            return None
        self.assertToken(self.token(), ')')
        pred = 'r_%s_1' % (tok)
        return [self._make_atom(pred, arg)] + conds

    def _handle_date(self, arg):
        #[]: +, []:'XXXX', [1004]:'04', []:'XX'
        conds = []
        self._parse_index_list()
        pol = self.token()#[1:-1]
        if pol == '+':
            conds.append(self._make_atom('r_pol_2',arg,'pos'))
        elif pol == '-':
            conds.append(self._make_atom('r_pol_2',arg,'neg'))
        self.assertToken(self.token(), ',')

        self._parse_index_list()
        year = self.token()#[1:-1]
        if year != 'XXXX':
            year = year.replace(':', '_')
            conds.append(self._make_atom('r_year_2',arg,year))
        self.assertToken(self.token(), ',')
        
        self._parse_index_list()
        month = self.token()#[1:-1]
        if month != 'XX':
            conds.append(self._make_atom('r_month_2',arg,month))
        self.assertToken(self.token(), ',')

        self._parse_index_list()
        day = self.token()#[1:-1]
        if day != 'XX':
            conds.append(self._make_atom('r_day_2',arg,day))

        return conds

    def _handle_time(self, arg):
        #time([1018]:'18', []:'XX', []:'XX')
        conds = []
        self._parse_index_list()
        hour = self.token()
        if hour != 'XX':
            conds.append(self._make_atom('r_hour_2',arg,hour))
        self.assertToken(self.token(), ',')

        self._parse_index_list()
        min = self.token()
        if min != 'XX':
            conds.append(self._make_atom('r_min_2',arg,min))
        self.assertToken(self.token(), ',')

        self._parse_index_list()
        sec = self.token()
        if sec != 'XX':
            conds.append(self._make_atom('r_sec_2',arg,sec))

        return conds

    def _handle_card(self, indices):
        #card(_G18535, 28, ge)
        self.assertToken(self.token(), '(')
        arg = self.token()
        self.assertToken(self.token(), ',')
        value = self.token()
        self.assertToken(self.token(), ',')
        rel = self.token()
        self.assertToken(self.token(), ')')
        return self._make_atom('r_card_3', arg, value, rel)

    def _handle_prop(self, indices):
        #prop(_G15949, drs(...))
        self.assertToken(self.token(), '(')
        arg = self.token()
        self.assertToken(self.token(), ',')
        drs = self.parse_Expression(None)
        self.assertToken(self.token(), ')')
        return drs

    def _make_atom(self, pred, *args):
        if isinstance(pred, str):
            pred = self._make_Variable(pred)
        if isinstance(pred, Variable):
            pred = DrtVariableExpression(pred)
        else:
            assert isinstance(pred, DrtAbstractVariableExpression), pred
        accum = pred

        for arg in args:
            if isinstance(arg, str):
                arg = self._make_Variable(arg)
            if isinstance(arg, Variable):
                arg = DrtVariableExpression(arg)
            else:
                assert isinstance(arg, DrtAbstractVariableExpression), arg
            accum = DrtApplicationExpression(accum, arg)
        return accum

    def _make_pred(self, pos, name, indices, arity):
        disc_id_str = '%s_' % self.discourse_id if self.discourse_id and indices else ''

        #TODO: removed since multiple indices mean it's not an occurrence word
        #assert len(indices) < 2, 'indices for %s: %s' % (f_name, indices)
        index_str = 's%s_w%s_' % indices[0] if self.occur_index and indices else ''

        if not indices:
            pos = 'r'

        return '%s_%s_%s%s%s' % (pos, name, disc_id_str, index_str, arity)

    def _parse_index_list(self):
        #[1001,1002]:
        indices = []
        self.assertToken(self.token(), '[')
        while self.token(0) != ']':
            base_index = int(self.token())
            sent_index = (base_index / 1000) - 1
            word_index = (base_index % 1000) - 1
            indices.append((sent_index, word_index))
            if self.token(0) == ',':
                self.token() #swallow ','
        self.token() #swallow ']'
        self.assertToken(self.token(), ':')
        return indices
    
    def parse_drs(self):
        #drs([[1001]:_G3943], 
        #    [[1002]:pred(_G3943, dog, n, 0)]
        #   )
        self.assertToken(self.token(), '(')
        self.assertToken(self.token(), '[')
        refs = []
        while self.token(0) != ']':
            indices = self._parse_index_list()
            refs.append(self._make_Variable(self.token()))
            if self.token(0) == ',':
                self.token() #swallow ','
        self.token() #swallow ']'
        self.assertToken(self.token(), ',')
        self.assertToken(self.token(), '[')
        conds = []
        while self.token(0) != ']':
            indices = self._parse_index_list()
            conds.extend(self.parse_condition(indices))
            if self.token(0) == ',':
                self.token() #swallow ','
        self.token() #swallow ']'
        self.assertToken(self.token(), ')')
        return DRS(refs, conds)

    def _make_binary_expression(self, constructor):
        self.assertToken(self.token(), '(')
        e1 = self.parse_Expression(None)
        self.assertToken(self.token(), ',')
        e2 = self.parse_Expression(None)
        self.assertToken(self.token(), ')')
        return constructor(e1, e2)

    def _handle_eq(self, indices):
        self.assertToken(self.token(), '(')
        e1 = DrtVariableExpression(self._make_Variable(self.token()))
        self.assertToken(self.token(), ',')
        e2 = DrtVariableExpression(self._make_Variable(self.token()))
        self.assertToken(self.token(), ')')
        return DrtEqualityExpression(e1, e2)

    def _handle_whq(self, indices):
        self.assertToken(self.token(), '(')
        self.assertToken(self.token(), '[')
#        c = 0
        ans_types = []
        while self.token(0) != ']':   #c > 0 or self.token(0) != ']':
#            if self.token(0) == '[':
#                c += 1
#            elif self.token(0) == ']':
#                c -= 1
            cat = self.token()
            self.assertToken(self.token(), ':')
            if cat == 'des':
                ans_types.append(self.token())
            elif cat == 'num':
                ans_types.append('number')
                typ = self.token()
                if typ == 'cou':
                    ans_types.append('count')
                else:
                    ans_types.append(typ)
            else:
                ans_types.append(self.token())
#            self.token() #swallow the token
        self.token() #swallow the ']'
        self.assertToken(self.token(), ',')
        d1 = self.parse_Expression(None)
        self.assertToken(self.token(), ',')
        ref = DrtVariableExpression(self._make_Variable(self.token()))
        self.assertToken(self.token(), ',')
        d2 = self.parse_Expression(None)
        self.assertToken(self.token(), ')')
        d3 = DRS([],[self._make_atom(self._make_pred('n', f_name, [], 1), ref) for f_name in ans_types])
        return ConcatenationDRS(d3,ConcatenationDRS(d1,d2))

    def _make_Variable(self, name):
        if name.startswith('_G'):
            name = 'z' + name[2:]
        return Variable(name)


class UnparseableInputException(Exception):
    pass


if __name__ == '__main__':
    opts = OptionParser("usage: %prog TEXT [options]")
    opts.add_option("--verbose", "-v", help="display verbose logs", action="store_true", default=False, dest="verbose")
    opts.add_option("--fol", "-f", help="output FOL", action="store_true", default=False, dest="fol")
    (options, args) = opts.parse_args()

    if len(args) != 1:
        opts.error("incorrect number of arguments")

    drs = Boxer().interpret(args[0], verbose=options.verbose)
    if drs is None:
        print None
    else:
        if options.fol:
            print drs.fol().normalize()
        else:
            drs.normalize().pprint()