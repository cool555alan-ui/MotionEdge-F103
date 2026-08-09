import csv,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from motionctl.attitude_metrics import (descriptive,drift_metrics,noise_metrics,percentile,
                                        regression,sequence_metrics,static_accuracy)
from motionctl.commands import RuntimeConfig
from motionctl.experiment import (ensure_stream_state,preserve_configuration,read_configuration,set_configuration,
                                  read_rows,write_rows)
from motionctl.phase08_report import generate_phase08_report
from motionctl.tuning import measured_candidate_metrics,score_candidates
from motionctl.tuning_profiles import SCORE_WEIGHTS

def row(target=0,measured=0,cross=0,repeat=1,sequence=10,timestamp=100):
    return {"target_deg":target,"reference_deg":target,"roll_deg":measured,"pitch_deg":cross,
            "repeat":repeat,"sample_sequence":sequence,"device_timestamp_ms":timestamp,"status_flags":0,
            "calibrated":True,"ax_mg":0,"ay_mg":0,"az_mg":1000,"gx_mdps":0,"gy_mdps":0,"gz_mdps":0,
            "host_monotonic_ns":1,"axis":"roll","phase":"test","disturbed":False}

class FakeClient:
    def __init__(self):self.config=RuntimeConfig();self.sets=0
    def request(self,command,payload=b"",retry=None):
        from motionctl import commands
        if command==commands.GET_CONFIG:return self.config.pack()
        if command==commands.SET_CONFIG:self.config=RuntimeConfig.unpack(payload);self.sets+=1;return b""
        if command==commands.SET_STREAM_STATE:
            self.config=RuntimeConfig(**{**self.config.__dict__,"telemetry_enabled":bool(payload[0])});return b""
        raise AssertionError(command)

class RecoveringClient(FakeClient):
    class Transport:
        def __init__(self,owner):self.owner=owner;self.reopened=False
        def close(self):pass
        def open(self):self.reopened=True;self.owner.available=True
    def __init__(self):
        super().__init__();self.available=False;self.flushed=False;self.transport=self.Transport(self)
    def request(self,command,payload=b"",retry=None):
        if not self.available:raise TimeoutError("blocked serial link")
        return super().request(command,payload,retry)
    def flush_input(self):self.flushed=True

class AppliedButTimedOutClient(FakeClient):
    def request(self,command,payload=b"",retry=None):
        from motionctl import commands
        if command==commands.SET_CONFIG:
            self.config=RuntimeConfig.unpack(payload)
            raise TimeoutError("response lost after apply")
        return super().request(command,payload,retry)

class Phase8Tests(unittest.TestCase):
    def test_descriptive_empty(self):self.assertEqual(descriptive([])["count"],0)
    def test_descriptive_single(self):self.assertEqual(descriptive([2])["stddev"],0)
    def test_descriptive_peak_to_peak(self):self.assertEqual(descriptive([1,4])["peak_to_peak"],3)
    def test_nan_rejected(self):
        with self.assertRaises(ValueError):descriptive([math.nan])
    def test_inf_rejected(self):
        with self.assertRaises(ValueError):descriptive([math.inf])
    def test_percentile(self):self.assertEqual(percentile([0,10],.5),5)
    def test_regression_exact(self):
        fit=regression([-1,0,1],[-2,0,2]);self.assertAlmostEqual(fit["slope"],2);self.assertEqual(fit["r_squared"],1)
    def test_regression_no_span(self):self.assertIsNone(regression([1,1],[2,3])["slope"])
    def test_static_missing_reference(self):self.assertEqual(static_accuracy([],"roll")["status"],"NOT_TESTED")
    def test_static_mae_rmse(self):
        rows=[row(-10,-9),row(10,12)];m=static_accuracy(rows,"roll");self.assertEqual(m["mae"],1.5);self.assertAlmostEqual(m["rmse"],math.sqrt(2.5))
    def test_static_max_error(self):self.assertEqual(static_accuracy([row(0,3)],"roll")["max_abs_error"],3)
    def test_repeatability(self):
        rows=[row(10,9,repeat=1),row(10,11,repeat=2)];self.assertGreater(static_accuracy(rows,"roll")["repeatability_stddev"],0)
    def test_hysteresis(self):
        rows=[row(10,9,repeat=1),row(10,12,repeat=2)];self.assertEqual(static_accuracy(rows,"roll")["hysteresis_max"],3)
    def test_cross_axis(self):
        rows=[row(-10,-10,-1),row(0,0,0),row(10,10,1)];self.assertAlmostEqual(static_accuracy(rows,"roll")["cross_axis_deg_per_10deg"],1)
    def test_sequence_continuous(self):self.assertTrue(sequence_metrics([10,20,30])["continuous"])
    def test_sequence_duplicate(self):self.assertEqual(sequence_metrics([10,10])["duplicates"],1)
    def test_sequence_regression(self):self.assertEqual(sequence_metrics([20,10])["regressions"],1)
    def test_sequence_gap(self):self.assertEqual(sequence_metrics([10,30])["gaps"],1)
    def test_noise_metrics(self):
        rows=[row(measured=v,sequence=i*10,timestamp=i*100) for i,v in enumerate((0,1,-1),1)];m=noise_metrics(rows);self.assertEqual(m["roll"]["peak_to_peak"],2)
    def test_drift_slope(self):
        rows=[]
        for i in range(1200):
            item=row(measured=i/600,sequence=(i+1)*10,timestamp=i*100);item["pitch_deg"]=0;rows.append(item)
        self.assertAlmostEqual(drift_metrics(rows)["roll"]["slope_deg_per_min"],1,places=2)
    def test_drift_short_not_tested(self):self.assertEqual(drift_metrics([row()])["status"],"NOT_TESTED")
    def test_weights_normalized(self):self.assertAlmostEqual(sum(SCORE_WEIGHTS.values()),1)
    def test_tuning_empty(self):self.assertEqual(score_candidates([]),[])
    def test_tuning_best(self):
        keys=SCORE_WEIGHTS;good={"name":"good",**{k:1 for k in keys}};bad={"name":"bad",**{k:2 for k in keys}}
        self.assertEqual(score_candidates([bad,good])[0]["name"],"good")
    def test_tuning_negative_rejected(self):
        candidate={k:1 for k in SCORE_WEIGHTS};candidate["drift"]=-1
        with self.assertRaises(ValueError):score_candidates([candidate])
    def test_measured_candidate_metrics(self):
        static=[];plus=[];minus=[];dynamic=[]
        for i in range(20):
            item=row(measured=.01*(i%2),sequence=(i+1)*10,timestamp=i*100);item["pitch_deg"]=0;item["gx_mdps"]=0;static.append(item)
            p=row(measured=30,sequence=(i+1)*10,timestamp=i*100);p["pitch_deg"]=1;plus.append(p)
            m=row(measured=-30,sequence=(i+1)*10,timestamp=i*100);m["pitch_deg"]=-1;minus.append(m)
            d=row(measured=min(30,i*3),sequence=(i+1)*10,timestamp=i*100);d["gx_mdps"]=10000 if i>2 else 0;dynamic.append(d)
        metrics=measured_candidate_metrics(static,plus,minus,dynamic)
        self.assertEqual(metrics["static_mae"],0);self.assertGreaterEqual(metrics["dynamic_lag"],0)
    def test_config_restored_after_exception(self):
        client=FakeClient()
        with self.assertRaises(RuntimeError):
            with preserve_configuration(client):client.config=RuntimeConfig(alpha_milli=500);raise RuntimeError("stop")
        self.assertEqual(client.config.alpha_milli,200)
    def test_stream_state_read_back(self):
        client=FakeClient();self.assertTrue(ensure_stream_state(client,True).telemetry_enabled)
    def test_config_read_recovers_after_reopen(self):
        client=RecoveringClient();self.assertEqual(read_configuration(client),RuntimeConfig())
        self.assertTrue(client.transport.reopened);self.assertTrue(client.flushed)
    def test_set_config_timeout_uses_readback(self):
        client=AppliedButTimedOutClient();wanted=RuntimeConfig(alpha_milli=150)
        self.assertEqual(set_configuration(client,wanted),wanted)
    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"rows.csv";write_rows(path,[row()]);self.assertEqual(read_rows(path)[0]["az_mg"],1000)
    def test_report_empty_protects_figures(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"root";out=Path(d)/"out";root.mkdir();result=generate_phase08_report(root,out)
            self.assertEqual(result["result"],"INCOMPLETE");self.assertTrue((out/"phase08-characterization-report.md").is_file())
    def test_report_reference_limited(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"root";out=Path(d)/"out";(root/"reference").mkdir(parents=True)
            (root/"reference"/"reference-setup.json").write_text(json.dumps({"reference_type":"phone","uncertainty_deg":None}))
            (root/"static-roll").mkdir();write_rows(root/"static-roll"/"static-used.csv",[row()])
            result=generate_phase08_report(root,out);self.assertEqual(result["checks"]["static_roll"],"REFERENCE_LIMITED")
    def test_30_minute_synthetic_pressure(self):
        rows=[row(measured=0.01*math.sin(i/20),sequence=(i+1)*10,timestamp=i*100) for i in range(18000)]
        self.assertEqual(noise_metrics(rows)["count"],18000)

if __name__=="__main__":unittest.main()
