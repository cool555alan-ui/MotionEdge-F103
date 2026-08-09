"""Phase 8 characterize/tune command-line surface."""

from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from .characterization import (candidate_experiment,continuous_experiment,coordinate_experiment,
                               dynamic_experiment,record_reference,static_experiment)
from .device import DeviceClient
from .phase08_report import generate_phase08_report
from .transport import SerialTransport
from .tuning import score_candidates

def _connection(parser):
    parser.add_argument("--port",required=True);parser.add_argument("--baud",type=int,default=115200);parser.add_argument("--timeout",type=float,default=1.0)

def add_phase08_parsers(subs)->None:
    root=subs.add_parser("characterize",help="Phase 8 attitude characterization")
    children=root.add_subparsers(dest="characterize_command",required=True)
    reference=children.add_parser("reference");reference.add_argument("--output",type=Path,default=Path("artifacts/phase08/reference"))
    coordinate=children.add_parser("coordinate");_connection(coordinate);coordinate.add_argument("--output",type=Path,default=Path("artifacts/phase08/coordinate"))
    static=children.add_parser("static");_connection(static);static.add_argument("--angles",default="-30,-20,-10,0,10,20,30")
    static.add_argument("--repeats",type=int,default=3);static.add_argument("--settle",type=float,default=5);static.add_argument("--capture",type=float,default=20)
    static.add_argument("--axis",choices=("roll","pitch"),required=True);static.add_argument("--output",type=Path,required=True)
    noise=children.add_parser("noise");_connection(noise);noise.add_argument("--duration",type=float,default=600);noise.add_argument("--output",type=Path,required=True)
    drift=children.add_parser("drift");_connection(drift);drift.add_argument("--duration",type=float,default=1800);drift.add_argument("--output",type=Path,required=True)
    dynamic=children.add_parser("dynamic");_connection(dynamic);dynamic.add_argument("--target-angle",type=float,default=30);dynamic.add_argument("--trials",type=int,default=10)
    dynamic.add_argument("--axis",choices=("roll","pitch"),default="roll");dynamic.add_argument("--output",type=Path,required=True)
    candidate=children.add_parser("candidate");_connection(candidate);candidate.add_argument("--name",required=True)
    candidate.add_argument("--alpha",type=float,required=True);candidate.add_argument("--gyro-weight",type=float,required=True)
    candidate.add_argument("--static-duration",type=float,default=120);candidate.add_argument("--output",type=Path,required=True)
    report=children.add_parser("report");report.add_argument("input",type=Path);report.add_argument("--output",type=Path,required=True)
    session=children.add_parser("session");_connection(session);session.add_argument("--output",type=Path,default=Path("artifacts/phase08"))
    tune=subs.add_parser("tune",help="rank measured Phase 8 parameter candidates");tune.add_argument("--input",type=Path,required=True);tune.add_argument("--output",type=Path,required=True)

def _client(args):return DeviceClient(SerialTransport(args.port,args.baud),timeout=args.timeout)
def _angles(text):
    values=[float(value.strip()) for value in text.split(",") if value.strip()]
    if not values:raise ValueError("angles cannot be empty")
    return values

def _tune(args)->int:
    path=args.input/"candidate-metrics.csv" if args.input.is_dir() else args.input
    if not path.is_file():raise ValueError(f"candidate metrics not found: {path}")
    with path.open("r",encoding="utf-8-sig",newline="") as stream:
        rows=[]
        for row in csv.DictReader(stream):
            parsed={key:(float(value) if key not in ("name",) else value) for key,value in row.items()}
            rows.append(parsed)
    ranking=score_candidates(rows);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"tuning-ranking.json").write_text(json.dumps(ranking,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (args.output/"tuning-ranking.csv").open("w",encoding="utf-8",newline="") as stream:
        fields=["rank","name","alpha","gyro_weight","total_score","static_mae","noise_stddev","peak_to_peak","dynamic_lag","overshoot","drift","cross_axis"]
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(ranking)
    print(json.dumps(ranking,ensure_ascii=False,indent=2));return 0

def run_phase08(args)->int:
    if args.command=="tune":return _tune(args)
    command=args.characterize_command
    if command=="reference":print(json.dumps(record_reference(args.output),ensure_ascii=False,indent=2));return 0
    if command=="report":
        result=generate_phase08_report(args.input,args.output);print(json.dumps({"result":result["result"],"output":str(args.output)},ensure_ascii=False));return 0
    if command=="session":
        root=args.output;record_reference(root/"reference")
        with _client(args) as client:
            coordinate_experiment(client,root/"coordinate",args.port,args.baud)
            static_experiment(client,root/"static-roll",[-30,-20,-10,0,10,20,30],3,5,20,"roll",args.port,args.baud)
            static_experiment(client,root/"static-pitch",[-30,-20,-10,0,10,20,30],3,5,20,"pitch",args.port,args.baud)
            continuous_experiment(client,root/"static-noise",600,"noise",args.port,args.baud)
            continuous_experiment(client,root/"long-drift",1800,"drift",args.port,args.baud)
            dynamic_experiment(client,root/"dynamic",30,10,"roll",args.port,args.baud)
        generate_phase08_report(root,root/"final-report");return 0
    with _client(args) as client:
        if command=="coordinate":result=coordinate_experiment(client,args.output,args.port,args.baud)
        elif command=="static":result=static_experiment(client,args.output,_angles(args.angles),args.repeats,args.settle,args.capture,args.axis,args.port,args.baud)
        elif command=="noise":result=continuous_experiment(client,args.output,args.duration,"noise",args.port,args.baud)
        elif command=="drift":
            if args.duration<1800:print("WARNING: duration below 1800 seconds; final drift status will be NOT_TESTED")
            result=continuous_experiment(client,args.output,args.duration,"drift",args.port,args.baud)
        elif command=="candidate":result=candidate_experiment(client,args.output,args.name,args.alpha,args.gyro_weight,args.static_duration,args.port,args.baud)
        else:result=dynamic_experiment(client,args.output,args.target_angle,args.trials,args.axis,args.port,args.baud)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
