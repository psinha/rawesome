# Copyright 2012-2013 Greg Horn
#
# This file is part of rawesome.
#
# rawesome is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# rawesome is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with rawesome.  If not, see <http://www.gnu.org/licenses/>.

import copy
import casadi as C
import matplotlib.pyplot as plt
import numpy
from numpy import pi
import pickle

import rawe
import rawekite
import kiteCallback

def setupOcp(dae,conf,nk=50,nicp=1,deg=4):
    ocp = rawe.collocation.Coll(dae, nk=nk,nicp=nicp,deg=deg)

    print "setting up collocation..."
    ocp.setupCollocation(ocp.lookup('endTime'))

    # constrain invariants
    def constrainInvariantErrs():
        dcm = ocp.lookup('dcm',timestep=0)
        err = C.mul(dcm.T,dcm)
        ocp.constrain( C.veccat([err[0,0] - 1, err[1,1]-1, err[2,2] - 1, err[0,1], err[0,2], err[1,2]]), '==', 0, tag=('initial dcm orthonormal',None))
        ocp.constrain(ocp.lookup('c',timestep=0), '==', 0, tag=('initial c 0',None))
        ocp.constrain(ocp.lookup('cdot',timestep=0), '==', 0, tag=('initial cdot 0',None))
    constrainInvariantErrs()

    # constrain line angle
    for k in range(0,nk):
        ocp.constrain(ocp.lookup('cos_line_angle',timestep=k),'>=',C.cos(55*pi/180), tag=('line angle',k))

    # constrain airspeed
    def constrainAirspeedAlphaBeta():
        for k in range(0,nk):
            ocp.constrain(ocp.lookup('airspeed',timestep=k), '>=', 20, tag=('airspeed',nk))
            ocp.constrainBnds(ocp.lookup('alpha_deg',timestep=k), (-5,15), tag=('alpha',nk))
            ocp.constrainBnds(ocp.lookup('beta_deg', timestep=k), (-10,10), tag=('beta',nk))
    constrainAirspeedAlphaBeta()

    # constrain tether force
    for k in range(nk):
        ocp.constrain( ocp.lookup('tether_tension',timestep=k,degIdx=1), '>=', 0, tag=('tether tension',(nk,0)))
        ocp.constrain( ocp.lookup('tether_tension',timestep=k,degIdx=ocp.deg), '>=', 0, tag=('tether tension',(nk,1)))

    # make it periodic
    for name in [ "y","z",
                  "dy","dz",
                  "w1","w2","w3",
                  'aileron','elevator'
                  ]:
        ocp.constrain(ocp.lookup(name,timestep=0),'==',ocp.lookup(name,timestep=-1))

    # periodic attitude
#    rawekite.kiteutils.periodicEulers(ocp)
#    rawekite.kiteutils.periodicOrthonormalizedDcm(ocp)
    rawekite.kiteutils.periodicDcm(ocp)

    # bounds
    ocp.bound('aileron',(-0.04,0.04))
    ocp.bound('elevator',(-0.1,0.1))
    ocp.bound('daileron',(-2.0,2.0))
    ocp.bound('delevator',(-2.0,2.0))
    ocp.bound('prop_drag',(0,1e4))

    ocp.bound('x',(-2000,2000))
    ocp.bound('y',(-2000,2000))
    if 'minAltitude' in conf:
        ocp.bound('z',(conf['minAltitude'],2000))
    else:
        ocp.bound('z',(0.5,2000))
    ocp.bound('r',(100,100))

    for e in ['e11','e21','e31','e12','e22','e32','e13','e23','e33']:
        ocp.bound(e,(-1.1,1.1))

    for d in ['dx','dy','dz']:
        ocp.bound(d,(-70,70))

    for w in ['w1','w2','w3']:
        ocp.bound(w,(-4*pi,4*pi))

    ocp.bound('endTime',(4.0,4.0))
    ocp.guess('endTime',4.0)
    ocp.bound('w0',(10,10))

    # boundary conditions
    ocp.bound('y',(0,0),timestep=0,quiet=True)

    return ocp


if __name__=='__main__':
    print "reading config..."
    from carousel_conf import conf
    conf['runHomotopy'] = True
    conf['minAltitude'] = 0.5
    nk = 40

    print "creating model..."
    dae = rawe.models.crosswind_drag_mode(conf)
    #dae = rawe.models.simpleCrosswind(conf)
    dae.addP('endTime')

    print "setting up ocp..."
    ocp = setupOcp(dae,conf,nk=nk)

    lineRadiusGuess = 70.0
    circleRadiusGuess = 15.0

    # trajectory for homotopy
    homotopyTraj = {'x':[],'y':[],'z':[]}
    k = 0
    for nkIdx in range(ocp.nk+1):
        for nicpIdx in range(ocp.nicp):
            if nkIdx == ocp.nk and nicpIdx > 0:
                break
            for degIdx in range(ocp.deg+1):
                if nkIdx == ocp.nk and degIdx > 0:
                    break

                r = circleRadiusGuess
                h = numpy.sqrt(lineRadiusGuess**2 - r**2)
                nTurns = 1

                # path following
                theta = nTurns*2*pi*k/float(ocp.nk*ocp.nicp*(ocp.deg+1)-1)

                thetaDot = nTurns*2*pi/(ocp._guess.lookup('endTime'))
                xyzCircleFrame    = numpy.array([h, r*numpy.sin(theta),          -r*numpy.cos(theta)])
                xyzDotCircleFrame = numpy.array([0, r*numpy.cos(theta)*thetaDot,  r*numpy.sin(theta)*thetaDot])

                phi = numpy.arcsin(r/lineRadiusGuess) # rotate so it's above ground
                phi += numpy.arcsin((conf['minAltitude']+0.3)/lineRadiusGuess)
                R_c2n = numpy.matrix([[ numpy.cos(phi), 0, -numpy.sin(phi)],
                                      [              0, 1,               0],
                                      [ numpy.sin(phi), 0,  numpy.cos(phi)]])
                xyz    = numpy.dot(R_c2n, xyzCircleFrame)
                xyzDot = numpy.dot(R_c2n, xyzDotCircleFrame)

                if nicpIdx == 0 and degIdx == 0:
                    homotopyTraj['x'].append(float(xyz[0,0]))
                    homotopyTraj['y'].append(float(xyz[0,1]))
                    homotopyTraj['z'].append(float(xyz[0,2]))

                x = float(xyz[0,0])
                y = float(xyz[0,1])
                z = float(xyz[0,2])

                dx = float(xyzDot[0,0])
                dy = float(xyzDot[0,1])
                dz = float(xyzDot[0,2])

                ocp.guess('x',x,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('y',y,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('z',z,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('dx',dx,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('dy',dy,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('dz',dz,timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)

                p0 = numpy.array([x,y,z])
                dp0 = numpy.array([dx,dy,dz])
                e1 = dp0/numpy.linalg.norm(dp0)
                e3 = p0/lineRadiusGuess
                e2 = numpy.cross(e3,e1)

                ocp.guess('e11',e1[0],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e12',e1[1],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e13',e1[2],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)

                ocp.guess('e21',e2[0],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e22',e2[1],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e23',e2[2],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)

                ocp.guess('e31',e3[0],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e32',e3[1],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)
                ocp.guess('e33',e3[2],timestep=nkIdx,nicpIdx=nicpIdx,degIdx=degIdx)

                k += 1

    ocp.guess('w3', 2*pi/ocp._guess.lookup('endTime'))

    # objective function
    obj = -1e6*ocp.lookup('gamma_homotopy')
    for k in range(ocp.nk+1):
        obj += (homotopyTraj['x'][k] - ocp.lookup('x',timestep=k))**2
        obj += (homotopyTraj['y'][k] - ocp.lookup('y',timestep=k))**2
        obj += (homotopyTraj['z'][k] - ocp.lookup('z',timestep=k))**2
    ocp.setQuadratureDdt('quadrature_energy', 'prop_power')

    # control regularization
    for k in range(ocp.nk):
        daileron = ocp.lookup('daileron',timestep=k)
        delevator = ocp.lookup('delevator',timestep=k)

        daileronSigma = 0.01
        delevatorSigma = 0.1

        ailObj = daileron*daileron / (daileronSigma*daileronSigma)
        eleObj = delevator*delevator / (delevatorSigma*delevatorSigma)

        obj += 1e-2*(ailObj + eleObj)/float(ocp.nk)

    # homotopy forces/torques regularization
    homoReg = 0
    for k in range(ocp.nk):
        for nicpIdx in range(ocp.nicp):
            for degIdx in range(1,ocp.deg+1):
                homoReg += ocp.lookup('f1_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
                homoReg += ocp.lookup('f2_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
                homoReg += ocp.lookup('f3_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
                homoReg += ocp.lookup('t1_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
                homoReg += ocp.lookup('t2_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
                homoReg += ocp.lookup('t3_homotopy',timestep=k,nicpIdx=nicpIdx,degIdx=degIdx)**2
    obj += 1e-2*homoReg/float(ocp.nk*ocp.nicp*ocp.deg)

    ocp.setObjective( obj )

    # initial guesses
    ocp.guess('w0',10)
    ocp.guess('r',lineRadiusGuess)

    for name in ['w1','w2','aileron','elevator','daileron','delevator','prop_drag']:
        ocp.guess(name,0)

    ocp.guess('gamma_homotopy',0)

    # spawn telemetry thread
    callback = rawe.telemetry.startTelemetry(ocp, conf,callbacks=
                                             [(kiteCallback.callback,'kite-optimization'),
                                              (rawekite.kiteTelemetry.showAllPoints,'multi-carousel')])

    # solver
    solverOptions = [("expand_f",True),
                     ("expand_g",True),
                     ("generate_hessian",True),
#                     ("qp_solver",C.NLPQPSolver),
#                     ("qp_solver_options",{'nlp_solver': C.IpoptSolver, "nlp_solver_options":{"linear_solver":"ma57"}}),
                     ("linear_solver","ma57"),
                     ("max_iter",1000),
                     ("tol",1e-11),
#                     ('monitor',['eval_g']),
#                     ("MaxIter",5000),
#                     ("Timeout", 1e6),
#                     ("UserHM", True),
#                     ("ScaleConIter",True),
#                     ("ScaledFD",True),
#                     ("ScaledKKT",True),
#                     ("ScaledObj",True),
#                     ("ScaledQP",True)
                     ]

    print "setting up solver..."
    ocp.setupSolver( solverOpts=solverOptions,
                     callback=callback )

    xInit = None
    ocp.bound('gamma_homotopy',(1e-4,1e-4),force=True)
    traj = ocp.solve(xInit=xInit)

    ocp.bound('gamma_homotopy',(0,1),force=True)
    traj = ocp.solve(xInit=traj.getDvs())

    ocp.bound('gamma_homotopy',(1,1),force=True)
#    ocp.bound('endTime',(4.0,4.0),force=True)
    traj = ocp.solve(xInit=traj.getDvs())

    traj.save("data/crosswind_homotopy.dat")

    def printBoundsFeedback():
        # bounds feedback
        lbx = ocp.solver.input(C.NLP_LBX)
        ubx = ocp.solver.input(C.NLP_UBX)
        ocp._bounds.printBoundsFeedback(xOpt,lbx,ubx,reportThreshold=0)
#    printBoundsFeedback()

    # Plot the results
    def plotResults():
        traj.subplot(['f1_homotopy','f2_homotopy','f3_homotopy'])
        traj.subplot(['t1_homotopy','t2_homotopy','t3_homotopy'])
        traj.subplot(['x','y','z'])
        traj.subplot(['dx','dy','dz'])
        traj.subplot([['aileron','elevator'],['daileron','delevator']],title='control surfaces')
        traj.subplot(['wind_at_altitude','dx'])
        traj.subplot(['c','cdot','cddot'],title="invariants")
        traj.plot('airspeed')
        traj.subplot([['alpha_deg','alphaTail_deg'],['beta_deg','betaTail_deg']])
        traj.subplot(['cL','cD','L_over_D'])
        traj.subplot(['prop_power', 'tether_tension'])
        traj.subplot(['w1','w2','w3'])
        traj.subplot(['e11','e12','e13','e21','e22','e23','e31','e32','e33'])
        traj.plot(['nu'])
        plt.show()
    plotResults()
