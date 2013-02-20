##################################################
#
#  Byron C. Wallace
#  Tufts Medical Center
#  OpenMeta[analyst]
#  ---
#  Binary data form module; for flexible entry of dichotomous
#  outcome data
##################################################
import pdb

from PyQt4.Qt import *
from PyQt4 import QtGui

import meta_py_r
from meta_globals import *

import ui_binary_data_form
from ui_binary_data_form import Ui_BinaryDataForm

# @TODO this should be an *application global*. It is now a
# global here and in the data_table_view class. (However
# here we show four digits; there it is 3. We want different
# levels of granularity).
NUM_DIGITS = 4 
ERROR_COLOR = QColor("red")
OK_COLOR = QColor("black")

# this is the maximum size of a residual that we're willing to accept
# when computing 2x2 data
THRESHOLD = 1e-5

class BinaryDataForm2(QDialog, ui_binary_data_form.Ui_BinaryDataForm):
    
    
    def __init__(self, ma_unit, cur_txs, cur_group_str, cur_effect, parent=None):
        super(BinaryDataForm2, self).__init__(parent)
        self.setupUi(self)
        self._setup_signals_and_slots()
        self.ma_unit = ma_unit
        self.raw_data_d = {}
        self.inconsistent = False
        for group in cur_txs:
            raw_data = self.ma_unit.get_raw_data_for_group(group)
            self.raw_data_d[group]  = raw_data
        
        self.cur_groups = cur_txs
        self.group_str = cur_group_str
        self.cur_effect = cur_effect
        self._update_raw_data() # ma_unit --> table
        self._populate_effect_data()
        self._update_data_table()
        
        # Setup inconsistency label
        inconsistency_palette = QPalette()
        inconsistency_palette.setColor(QPalette.WindowText,Qt.red)
        self.inconsistencyLabel.setPalette(inconsistency_palette)
        self.inconsistencyLabel.setVisible(False)
        
    def _setup_signals_and_slots(self):
        QObject.connect(self.raw_data_table, SIGNAL("cellChanged (int, int)"), 
                                                    self._cell_changed)
        QObject.connect(self.effect_cbo_box, SIGNAL("currentIndexChanged(QString)"),
                                                    self.effect_changed) 
                                                                                
        QObject.connect(self.effect_txt_box, SIGNAL("textChanged(QString)"), lambda new_text : self.val_edit("est", new_text))
        QObject.connect(self.low_txt_box, SIGNAL("textChanged(QString)"), lambda new_text : self.val_edit("lower", new_text))
        QObject.connect(self.high_txt_box, SIGNAL("textChanged(QString)"), lambda new_text : self.val_edit("upper", new_text))                                                                                            

                                                                             
    def _populate_effect_data(self):
        q_effects = sorted([QString(effect_str) for effect_str in self.ma_unit.effects_dict.keys()])
        self.effect_cbo_box.blockSignals(True)
        self.effect_cbo_box.addItems(q_effects)
        self.effect_cbo_box.blockSignals(False)
        self.effect_cbo_box.setCurrentIndex(q_effects.index(QString(self.cur_effect)))
        # populate fields with current effect data
        self.set_current_effect()

    def set_current_effect(self):
        '''Populates text boxes with effects (computed values) from ma unit'''
        effect_dict = self.ma_unit.effects_dict[self.cur_effect][self.group_str]
        for s, txt_box in zip(['display_est', 'display_lower', 'display_upper'], \
                              [self.effect_txt_box, self.low_txt_box, self.high_txt_box]):
            if effect_dict[s] is not None:
                txt_box.setText(QString("%s" % round(effect_dict[s], NUM_DIGITS)))
            else:
                txt_box.setText(QString(""))
            
    def effect_changed(self):
        '''Called when a new effect is selected in the combo box'''
        self.cur_effect = unicode(self.effect_cbo_box.currentText().toUtf8(), "utf-8")
        self.try_to_update_cur_outcome()
        self.set_current_effect()
        
    def val_edit(self, val_str, display_scale_val):
        ''' val_str is one of `est`, `lower`, `upper` '''
        
        try:
            display_scale_val = float(display_scale_val)
        except:
            # a number wasn't entered; ignore
            # should probably clear out the box here, too.
            print "fail."
            return None
            
        calc_scale_val = meta_py_r.binary_convert_scale(display_scale_val, \
                                        self.cur_effect, convert_to="calc.scale")
                      
        if val_str == "est":
            self.ma_unit.set_effect(self.cur_effect, self.group_str, calc_scale_val)
            self.ma_unit.set_display_effect(self.cur_effect, self.group_str, display_scale_val)
        elif val_str == "lower":
            self.ma_unit.set_lower(self.cur_effect, self.group_str, calc_scale_val)
            self.ma_unit.set_display_lower(self.cur_effect, self.group_str, display_scale_val)
        else:
            self.ma_unit.set_upper(self.cur_effect, self.group_str, calc_scale_val)
            self.ma_unit.set_display_upper(self.cur_effect, self.group_str, display_scale_val)
        
    def _update_raw_data(self):
        ''' Generates the 2x2 table with whatever parametric data was provided '''
        ''' Sets #events and #subjects in binary table'''
        self.raw_data_table.blockSignals(True)
        for row, group in enumerate(self.cur_groups):
            for col in (0,2):
                adjusted_index = 0 if col==0 else 1
                val = self.raw_data_d[group][adjusted_index]
                if val is not None:
                    try:
                        val = str(int(val))
                    except:
                        val = str(val)
                    item = QTableWidgetItem(val)
                    self.raw_data_table.setItem(row, col, item)
        self.raw_data_table.blockSignals(False)
      
    def _update_ma_unit(self):
        ''' Copy data from binary data form table to the MA_unit'''
        ''' 
        Walk over the entries in the matrix (which may have been updated
        via imputation in the _cell_changed method) corresponding to the 
        raw data in the underlying meta-analytic unit and update the values.
        '''
        for row in range(2):
            for col in (0,2):
                adjusted_col = 1 if col==2 else 0
                self.raw_data_d[self.cur_groups[row]][adjusted_col] = self._get_int(row, col)
                print "%s, %s: %s" % (row, col, self._get_int(row, col))
        print "ok -- raw data is now: %s" % self.raw_data_d
        
    def _cell_changed(self, row, col):
        # tries to make sense of user input before passing
        # on to the R routine
        
        # Used to be _fillin_basics _fillin_basics(self, row, col):
        self._update_ma_unit() # table --> ma_unit
        # _update_raw_data results in the 1,0 being "None"
        self._update_raw_data() # ma_unit --> table
        ####self._update_data_table()  # comment out to see if new R fillin.2x2.simpler works
        #self.check_for_consistencies()
        
        
        params = self._get_vals()
        print "Params: ", params
        
        computed_parameters = self._compute_2x2_table(params)
        if computed_parameters:
            self._set_vals(computed_parameters) # computed --> table widget
            
        self.check_for_consistencies()
        
        
        # need to try and update metric here     
        self._update_ma_unit() # table widget --> ma_unit
        self.try_to_update_cur_outcome()
        
    def _get_vals(self):
        ''' Package table from 2x2 table in to a dictionary'''
        
        vals_d = {}
        vals_d["c11"] = self._get_int(0, 0)
        vals_d["c12"] = self._get_int(0, 1)
        vals_d["c21"] = self._get_int(1, 0)
        vals_d["c22"] = self._get_int(1, 1)
        vals_d["r1sum"] = self._get_int(0, 2)
        vals_d["r2sum"] = self._get_int(1, 2)
        vals_d["c1sum"] = self._get_int(2, 0)
        vals_d["c2sum"] = self._get_int(2, 1)
        vals_d["total"] = self._get_int(2, 2)
        return vals_d
        
         
    def _set_vals(self, computed_d):
        '''Sets values in table widget'''
        self.raw_data_table.blockSignals(True)
        self._set_val(0, 0, computed_d["c11"])
        self._set_val(0, 1, computed_d["c12"])
        self._set_val(1, 0, computed_d["c21"])
        self._set_val(1, 1, computed_d["c22"])  
        self._set_val(0, 2, computed_d["r1sum"])
        self._set_val(1, 2, computed_d["r2sum"])
        self._set_val(2, 0, computed_d["c1sum"])
        self._set_val(2, 1, computed_d["c2sum"])  
        self._set_val(2, 2, computed_d["total"])  
        
        #pyqtRemoveInputHook()
        #pdb.set_trace()
        self.raw_data_table.blockSignals(False)
        
    def _set_val(self, i, j, val):
        is_NaN = lambda x: x != x
        if val >= 0 and not is_NaN(val):
            self._set_table_cell(i, j, val)
        
    def _set_table_cell(self, i, j, val):
        # try to cast to an int
        try:
            val = int(round(val))
        except:
            pass
        self.raw_data_table.setItem(i, j, \
                 QTableWidgetItem(str(val)))     
        
    def _build_dict(self):
        d =  dict(zip(["control.n.outcome", "control.N", "tx.n.outcome", "tx.N"], self.raw_data))
        print "\n!%s" % self.ma_unit.effects_dict[self.cur_effect]
        d["estimate"] = self.ma_unit.effects_dict[self.cur_effect][self.group_str]['est']
        print d["estimate"] == ""
        print d["estimate"] is None
        return d
        
    def check_for_consistencies(self):
        self.inconsistent = False
        self.check_that_rows_sum()
        self.check_that_cols_sum()
        
        if self.inconsistent:
            #show label, disable OK buttonbox button
            self.inconsistencyLabel.setVisible(True)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self.inconsistencyLabel.setVisible(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        
    def check_that_rows_sum(self):
        for row in range(3):
            if self._row_is_populated(row):
                row_sum = 0
                for col in range(2):
                    row_sum += self._get_int(row, col)
                if not row_sum == self._get_int(row, 2):
                    self._color_row(row)
                    self.inconsistent = True
                    
    def check_that_cols_sum(self):
        # TODO
        pass
        for col in range(3):
            if self._col_is_populated(col):
                col_sum = 0
                for row in range(2):
                    col_sum += self._get_int(row,col)
                if not col_sum == self._get_int(2,col):
                    self._color_col(col)
                    self.inconsistent = True
        
    def _color_all(self, color=ERROR_COLOR):
        self.raw_data_table.blockSignals(True)
        for row in range(3):
            for col in range(3):
                print "setting row: %s, col: %s" % (row, col)
                item = self.raw_data_table.item(row, col)
                if item is not None:
                    item.setTextColor(color)
        self.raw_data_table.blockSignals(False)
        
             
        
    def _color_row(self, row):
        self.raw_data_table.blockSignals(True)
        error_color = QColor("red")
        for col in range(3):
            print "setting row: %s, col: %s" % (row, col)
            self.raw_data_table.item(row, col).setTextColor(error_color)
        self.raw_data_table.blockSignals(False)
        
    def _color_col(self, col):
        self.raw_data_table.blockSignals(True)
        error_color = QColor("red")
        for row in range(3):
            print "setting row: %s, col: %s" % (row, col)
            self.raw_data_table.item(row, col).setTextColor(error_color)
        self.raw_data_table.blockSignals(False)
        
    def _row_is_populated(self, row):
        return not True in [self._is_empty(row, col) for col in range(2)]
    def _col_is_populated(self, col):
        return not True in [self._is_empty(row, col) for row in range(2)]
    
    def _compute_2x2_table(self,params):
        ''' Computes values for the 2x2 table if possible'''
        
        computed = meta_py_r.fillin_2x2(params)
        print "Computed: ", computed 
        
        if computed != None: # more than one value entered
            abs_residuals = [abs(x) for x in computed['residuals']]
            if max(abs_residuals ) > THRESHOLD:
                print "problem computing 2x2 table."
                print "max residual: %s" % max(computed['residuals'])
                print computed['residuals']
                print ("Coefficients: ", computed['coefficients'])
                return None
            else: # values are hunky-dory
                print "table computed successfully!"
                return computed["coefficients"]
                #self._set_vals(computed["coefficients"]) # computed --> table widget
        return None
        
    def _update_data_table(self):        
        '''
        boring code that tries to compute/fill-in the basic 2x2 table from
        provided information. sort of verbose, should probably make more 
        concise.
        '''
        self.raw_data_table.blockSignals(True)
        # now compute the numbers with no events, if possible.
        # 
        # the raw data is of the form g_n / g_N where g_N is the *total* 
        # and g_n is the event count. thus no event = g_N - g_n.
        raw_data_list = []
        for group in self.cur_groups:
            raw_data_list.extend(self.raw_data_d[group])
        
        e1, n1, e2, n2 = [int(x) if (x != "" and x is not None) else None for x in raw_data_list]
        
        print "updating raw data with:\n e1 = %s, n1 = %s, e2 = %s, n2 = %s" % \
                                            (e1, n1, e2, n2)
        
        ###### NEW STUFF ######
        # set up parameters for R fill-in
        params = {}
        params["c11"] = e1
        params["c12"] = None
        params["c21"] = e2
        params["c22"] = None
        params["r1sum"] = n1
        params["r2sum"] = n2
        params["c1sum"] = None
        params["c2sum"] = None
        params["total"] = None
        
        computed_params = self._compute_2x2_table(params)
        (total_events,total_no_events,total_total_events) = (None,None,None)
        if computed_params:
            self._set_vals(computed_params) # computed --> table widget
            # Set the following values explicitly even though they may conflict
            # with the values given by computed_params. If they do, let the consistency
            # checker catch it and alert the user.
            self.raw_data_table.blockSignals(True)
            self._set_val(0, 0, e1)
            self._set_val(1, 0, e2)
            self._set_val(0, 2, n1)
            self._set_val(1, 2, n2)
            self.raw_data_table.blockSignals(False)
        
            # this is just here to get the inconsistency stuff below to work with minimal effort
            total_events    = computed_params["c1sum"]
            total_no_events = computed_params["c2sum"]
            total_total_events = computed_params["total"]
            try:
                total_events = int(round(total_events))
                total_no_events = int(round(total_no_events))
                total_total_events = int(round(total_total_events))
            except:
                raise Exception("Could not convert to int while trying update the binary calculator table")
                      
        self.inconsistent = False
        if not any([x is None or x=="" for x in (n1, n2, total_events, total_no_events)]):
            if n1 < 0 or n2 < 0 or not (n1 + n2 == total_events + total_no_events == total_total_events):
                self._color_all()
                self.inconsistent = True
                print "------\nhello1"
                print "n1:",n1,"n2:",n2,"total_events:",total_events,"total_no_events:",total_no_events,"total_total_events:",total_total_events
                
        if not any([x is None or x=="" for x in (total_events, total_no_events)]):
            if total_events < 0 or total_no_events < 0:
                self._color_all()
                self.inconsistent = True
                print "hello2"
        
        if not any([x is None or x=="" for x in (total_events, total_no_events, n1, n2)]):
            if not (n1 + n2 == total_events + total_no_events == total_total_events):
                self._color_all()
                self.inconsistent = True
                print "hello3"
        
        # finally, check the whole thing for negative numbers
        for row in range(3):
            for col in range(3):
                val = self._get_int(row, col)
                if val is not None and val != "" and val < 0:
                    self._color_all()
                    self.inconsistent = True
                
        if not self.inconsistent:
            self._color_all(color=OK_COLOR)
                
        self.raw_data_table.blockSignals(False)
        
        
    def _is_empty(self, i, j):
        val = self.raw_data_table.item(i,j)
        return val is None or val.text() == ""
        

    def _get_int(self, i, j):
        if not self._is_empty(i,j):
            int_val = int(float(self.raw_data_table.item(i, j).text()))
            return int_val
        else:
            return None # its good to be explicit
            
    def _none_or_empty(self, x):
        return x is None or x == ""
        
    def try_to_update_cur_outcome(self):
        e1, n1, e2, n2 = self.ma_unit.get_raw_data_for_groups(self.cur_groups)
        # if None is in the raw data, should we clear out current outcome?
        if not any([self._none_or_empty(x) for x in [e1, n1, e2, n2]]) or \
                        (not any([self._none_or_empty(x) for x in [e1, n1]]) and self.cur_effect in BINARY_ONE_ARM_METRICS):
            if self.cur_effect in BINARY_TWO_ARM_METRICS:
                est_and_ci_d = meta_py_r.effect_for_study(e1, n1, e2, n2, metric=self.cur_effect)
            else:
                # binary, one-arm
                est_and_ci_d = meta_py_r.effect_for_study(e1, n1, \
                                            two_arm=False, metric=self.cur_effect)
        
            display_est, display_low, display_high = est_and_ci_d["display_scale"]
            self.ma_unit.set_display_effect_and_ci(self.cur_effect, self.group_str, display_est, display_low, display_high)                            
            est, low, high = est_and_ci_d["calc_scale"] # calculation (e.g., log) scale
            self.ma_unit.set_effect_and_ci(self.cur_effect, self.group_str, est, low, high)
            self.set_current_effect()
           
        
