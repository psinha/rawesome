import zmq
#import time
#import os

import numpy
from numpy import pi
import copy

import casadi as C

import kite_pb2
import kiteproto

from collocation import Coll
import model

#tc0 = 2*389.970797939731

x0 = C.DMatrix( [ 1.154244772411
                , -0.103540608242
                , -0.347959211327
                , 0.124930983341
                , 0.991534857363
                , 0.035367725910
                , 0.316039689643
                , -0.073559821379
                , 0.945889986864
                , 0.940484536806
                , -0.106993361072
                , -0.322554269411
                , 0.000000000000
                , 0.000000000000
                , 0.000000000000
                , 0.137035790811
                , 3.664945343102
                , -1.249768772258
                , 0.000000000000
                , 3.874600000000
                ])
x0=C.veccat([x0,C.sqrt(C.sumAll(x0[0:2]*x0[0:2])),0])

def main():
    nk = 40

    print "creating model"
    dae = model.model(-0.01,extraParams=['endTime'])

    print "setting up OCP"
    nicp = 1
    deg = 4
    ocp = Coll(dae, nk=nk,nicp=nicp,deg=deg)

    # make the integrator
    print "setting up dynamics constraints"

    # constrain invariants
    def invariantErrs():
        dcm = C.horzcat( [ C.veccat([dae.x('e11'), dae.x('e21'), dae.x('e31')])
                         , C.veccat([dae.x('e12'), dae.x('e22'), dae.x('e32')])
                         , C.veccat([dae.x('e13'), dae.x('e23'), dae.x('e33')])
                         ] ).trans()
        err = C.mul(dcm.trans(), dcm)
        dcmErr = C.veccat([ err[0,0]-1, err[1,1]-1, err[2,2]-1, err[0,1], err[0,2], err[1,2] ])
        f = C.SXFunction( [dae.xVec(),dae.uVec(),dae.pVec()]
                        , [dae.output('c'),dae.output('cdot'),dcmErr]
                        )
        f.setOption('name','invariant errors')
        f.init()
        return f
    
    [c0,cdot0,dcmError0] = invariantErrs().call([ocp.xVec(0),ocp.uVec(0),ocp.pVec()])
    ocp.constrain(c0,'==',0)
    ocp.constrain(cdot0,'==',0)
    ocp.constrain(dcmError0,'==',0)

    # bounds
    ocp.bound('aileron',(-0.04,0.04))
    ocp.bound('elevator',(-0.1,0.1))

    ocp.bound('x',(0,4))
    ocp.bound('y',(-3,3))
    ocp.bound('z',(-2,3))
    ocp.bound('r',(1,2))
    ocp.bound('dr',(-1,1))
    ocp.bound('ddr',(0,0))
    ocp.bound('r',(1.2,1.2),timestep=0)

    for e in ['e11','e21','e31','e12','e22','e32','e13','e23','e33']:
        ocp.bound(e,(-1.1,1.1))

    for d in ['dx','dy','dz']:
        ocp.bound(d,(-50,50))

    for w in ['w1','w2','w3']:
        ocp.bound(w,(-8*pi,8*pi))

    ocp.bound('delta',(-0.01,1.01*2*pi))
    ocp.bound('ddelta',(-pi/4,8*pi))
    ocp.bound('tc',(-200,1000))
#    ocp.bound('tc',(389.970797939731,389.970797939731))
    ocp.bound('endTime',(0.5,2.0))
#    ocp.bound('endTime',(1.6336935276077966,1.6336935276077966))
    ocp.bound('w0',(0,0))

    # boundary conditions
    ocp.bound('delta',(0,0),timestep=0)
    ocp.bound('delta',(2*pi,2*pi),timestep=-1)

    # make it periodic
    states0 = ocp.xVec(0)
    statesF = ocp.xVec(-1)
    actions0 = ocp.uVec(0)
    actionsF = ocp.uVec(-1)
    for name in [ #"x"   # state 0
                  "y"   # state 1
                , "z"   # state 2
#                , "e11" # state 3
#                , "e12" # state 4
#                , "e13" # state 5
#                , "e21" # state 6
#                , "e22" # state 7
#                , "e23" # state 8
#                , "e31" # state 9
#                , "e32" # state 10
#                , "e33" # state 11
#                , "dx"  # state 12
                , "dy"  # state 13
                , "dz"  # state 14
                , "w1"  # state 15
                , "w2"  # state 16
                , "w3"  # state 17
#                , "delta" # state 18
                , "ddelta" # state 19
                , "r" # state 20
                , "dr" # state 21
                ]:
        ocp.constrain(ocp.lookup(name,timestep=0),'==',ocp.lookup(name,timestep=-1))

    # make the solver
    # objective function
    tc0 = 390
    obj = 0
    for k in range(nk):
        u = ocp.uVec(k)
        obj += (C.sumAll(u[0:2]*u[0:2]) + 1e-10*C.sumAll((u[2]-tc0)*(u[2]-tc0)))*ocp.lookup('endTime')
    ocp.setObjective(obj)

    # zero mq setup
    context   = zmq.Context(1)
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://*:5563")

    # callback function
    class MyCallback:
      def __init__(self):
        self.iter = 0 
      def __call__(self,f,*args):
          self.iter = self.iter + 1
          xOpt = numpy.array(f.input(C.NLP_X_OPT))

          xup,blah = ocp.devectorize(xOpt)
          
          kiteProtos = []
          for k in range(0,nk):
              j = nicp*(deg+1)*k
              kiteProtos.append( kiteproto.toKiteProto(C.DMatrix(blah['x'][:,j]),C.DMatrix(blah['u'][:,j]),C.DMatrix(blah['p'])) )
#          kiteProtos = [kiteproto.toKiteProto(C.DMatrix(blah['x'][:,k]),C.DMatrix(blah['u'][:,k]),C.DMatrix(blah['p'])) for k in range(blah['x'].shape[1])]

          ko = kite_pb2.KiteOpt()
          ko.css.extend(list(kiteProtos))

          ko.endTime = xup['endTime']
          ko.wind_x = xup['w0']
          ko.iters = self.iter
          publisher.send_multipart(["carousel-opt", ko.SerializeToString()])


    # solver
    solverOptions = [ ("linear_solver","ma57")
#                    , ("derivative_test","first-order")
                    , ("expand_f",True)
                    , ("expand_g",True)
#                    , ("generate_hessian",True)
#                    , ("max_iter",1000)
                    , ("tol",1e-4)
                    ]
    
    # initial conditions
    ocp.guessX(x0)
    for k in range(0,nk+1):
        val = 2.0*pi*k/nk
        ocp.guess('delta',val,timestep=k,quiet=True)

    ocp.guess('aileron',0)
    ocp.guess('elevator',0)
    ocp.guess('tc',389.970797939731)
    ocp.guess('endTime',1.6336935276077966)

    ocp.guess('ddr',0)
    ocp.guess('w0',5)

    (opt,blah) = ocp.run( ocp.lookup('endTime'),
                          solverOpts=solverOptions,
                          callback=MyCallback() )

if __name__=='__main__':
    main()
