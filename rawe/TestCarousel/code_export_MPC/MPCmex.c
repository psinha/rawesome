

#include "mex.h"

#include "acado.h"

#include "auxiliary_functions.c"


/* SOME CONVENIENT DEFINTIONS: */
/* --------------------------------------------------------------- */
/*    #define NX          22     /* number of differential states  */
/*    #define NU          3      /* number of control inputs       */
/*     #define N           5      /* number of control intervals    */
   #define NUM_STEPS   1      /* number of real time iterations */
   #define VERBOSE     1      /* show iterations: 1, silent: 0  */
/* --------------------------------------------------------------- */


/* GLOBAL VARIABLES FOR THE ACADO REAL-TIME ALGORITHM: */
/* --------------------------------------------------- */
   ACADOvariables acadoVariables;
   ACADOworkspace acadoWorkspace;

/* GLOBAL VARIABLES FOR THE QP SOLVER: */
/* ----------------------------------- */
   Vars         vars;
   Params       params;


/* A TEMPLATE FOR TESTING THE REAL-TIME IMPLEMENTATION: */
/* ---------------------------------------------------- */
void mexFunction( int            nlhs, 
                  mxArray        *plhs[], 
                  int            nrhs, 
                  const mxArray  *prhs[]){

    
    /* Input */
    int nRx0, nCx0; /*dimensions of first input argument*/
    double *dPx0; /*data pointer for the first input argument*/
    int nRxInit, nCxInit; 
    double *dPxInit; 
    int nRuInit, nCuInit; 
    double *dPuInit; 
    int nRin_xRef, nCin_xRef; 
    double *dPin_xRef; 
    int nRin_uRef, nCin_uRef; 
    double *dPin_uRef; 
    int nR_Q, nC_Q; 
    double *dP_Q; 
    int nR_R, nC_R; 
    double *dP_R;
    int nR_QT, nC_QT; 
    double *dP_QT; 
    int nR_lb, nC_lb; 
    double *dP_lb; 
    int nR_ub, nC_ub; 
    double *dP_ub; 
    /* Output */
    double *dPoutU; /*data pointer for the output argument*/
    double *dPoutX; 
    
    /* Initial State */
    nRx0      = mxGetM(prhs[0]);
    nCx0      = mxGetN(prhs[0]);
    dPx0      = mxGetPr(prhs[0]);
    /* Initial guess */
    nRxInit   = mxGetM(prhs[1]);
    nCxInit   = mxGetN(prhs[1]);
    dPxInit   = mxGetPr(prhs[1]);
    nRuInit   = mxGetM(prhs[2]);
    nCuInit   = mxGetN(prhs[2]);
    dPuInit   = mxGetPr(prhs[2]);
    /* Reference */
    nRin_xRef = mxGetM(prhs[3]);
    nCin_xRef = mxGetN(prhs[3]);
    dPin_xRef = mxGetPr(prhs[3]);
    nRin_uRef = mxGetM(prhs[4]);
    nCin_uRef = mxGetN(prhs[4]);
    dPin_uRef = mxGetPr(prhs[4]);
    /* Weighting matrices */
    nR_Q      = mxGetM(prhs[5]);
    nC_Q      = mxGetN(prhs[5]);
    dP_Q      = mxGetPr(prhs[5]);
    nR_R      = mxGetM(prhs[6]);
    nC_R      = mxGetN(prhs[6]);
    dP_R      = mxGetPr(prhs[6]);
    nR_QT     = mxGetM(prhs[7]);
    nC_QT     = mxGetN(prhs[7]);
    dP_QT     = mxGetPr(prhs[7]);
    
    
    /*checking input dimensions*/
    if ( nRx0*nCx0 != ACADO_NX ){
        mexPrintf( "First argument must be a matrix of size: %d \n", ACADO_NX );
        mexErrMsgTxt( "Check the dimensions of the first input array (initial state)" );
    }
    if ( ( nRxInit != ACADO_N+1 ) || ( nCxInit != ACADO_NX ) ){
        mexPrintf( "Second argument must be a matrix of size: %d by %d \n", ACADO_N+1, ACADO_NX );
        mexErrMsgTxt( "Check the dimensions of the second input array (initial guess for the states)" );
    }
    if ( ( nRuInit != ACADO_N ) || ( nCuInit != ACADO_NU ) ){
        mexPrintf( "Third argument must be a matrix of size: %d by %d \n", ACADO_N, ACADO_NU );
        mexErrMsgTxt( "Check the dimensions of the third input array (initial guess for the controls)" );
    }
    if ( ( nRin_xRef != ACADO_N ) || ( nCin_xRef != ACADO_NX ) ){
        mexPrintf( "Fourth argument must be a matrix of size: %d by %d \n", ACADO_N, ACADO_NX );
        mexErrMsgTxt( "Check the dimensions of the fourth input array (reference for the states)" );
    }
    if ( ( nRin_uRef != ACADO_N ) || ( nCin_uRef != ACADO_NU ) ){
        mexPrintf( "Fifth argument must be a matrix of size: %d by %d \n", ACADO_N, ACADO_NU );
        mexErrMsgTxt( "Check the dimensions of the fifth input array (reference for the controls)" );
    }
    if ( ( nR_Q != ACADO_NX ) || ( nC_Q != ACADO_NX ) ){
        mexPrintf( "Sixth argument must be a matrix of size: %d by %d \n", ACADO_NX, ACADO_NX );
        mexErrMsgTxt( "Check the dimensions of the sixth input array (state weighting matrix)" );
    }
    if ( ( nR_R != ACADO_NU ) || ( nC_R != ACADO_NU ) ){
        mexPrintf( "Seventh argument must be a matrix of size: %d by %d \n", ACADO_NU, ACADO_NU );
        mexErrMsgTxt( "Check the dimensions of the seventh input array (control weighting matrix)" );
    }
    if ( ( nR_QT != ACADO_NX ) || ( nC_QT != ACADO_NX ) ){
        mexPrintf( "Eighth argument must be a matrix of size: %d by %d \n", ACADO_NX, ACADO_NX );
        mexErrMsgTxt( "Check the dimensions of the eighth input array (terminal cost weighting matrix)" );
    }
    
    
    
    
   /* INTRODUCE AUXILIARY VAIRABLES: */
   /* ------------------------------ */
      int    i, j, iter        ;
      real_t measurement[ACADO_NX];

   /* INITIALIZE THE STATES AND CONTROLS: */
   /* ---------------------------------------- */
    for( j = 0; j < ACADO_N+1; ++j ) {
        for( i = 0; i < ACADO_NX  ; ++i ) {
            acadoVariables.x[j*ACADO_NX + i] = dPxInit[j + i*(ACADO_N+1)];
        }
    }
    for( j = 0; j < ACADO_N; ++j ) {
        for( i = 0; i < ACADO_NU; ++i ) {
            acadoVariables.u[j*ACADO_NU + i] = dPuInit[j + i*ACADO_N];
        }
    }

   /* INITIALIZE THE STATES AND CONTROL REFERENCE: */
   /* -------------------------------------------- */
    for( j = 0; j < ACADO_N; ++j ) {
        for( i = 0; i < ACADO_NX  ; ++i ) {
            acadoVariables.xRef[j*ACADO_NX + i] = dPin_xRef[j + i*ACADO_N];
        }
    }
    for( j = 0; j < ACADO_N; ++j ) {
        for( i = 0; i < ACADO_NU; ++i ) {
            acadoVariables.uRef[j*ACADO_NU + i] = dPin_uRef[j + i*ACADO_N];
        }
    }


   /* SETUP THE FIRST STATE MEASUREMENT: */
   /* ------------------------------------------------ */
    for( i = 0; i < ACADO_NX; ++i ) {
      measurement[i] = dPx0[i];
    }

   /* SETUP THE WEIGHTING MATRICES: */
   /* ------------------------------------------------ */
    for( j = 0; j < ACADO_NX; ++j ) {
        for( i = 0; i < ACADO_NX; ++i ) {
            acadoVariables.QQ[j*ACADO_NX + i] = dP_Q[j + i*ACADO_NX];
        }
    }
    for( j = 0; j < ACADO_NU; ++j ) {
        for( i = 0; i < ACADO_NU; ++i ) {
            acadoVariables.RR[j*ACADO_NU + i] = dP_R[j + i*ACADO_NU];
        }
    }
    for( j = 0; j < ACADO_NX; ++j ) {
        for( i = 0; i < ACADO_NX; ++i ) {
            acadoVariables.QT[j*ACADO_NX + i] = dP_QT[j + i*ACADO_NX];
        }
    }
      
      

	int status;

      real_t t0 = getTime();
   /* PREPARE FIRST STEP: */
   /* ------------------- */
      preparationStep();
      

   /* GET THE TIME BEFORE START THE LOOP: */
   /* ---------------------------------------------- */
      real_t t1 = getTime();
      real_t t2;

   /* THE REAL-TIME ITERATION LOOP: */
   /* ---------------------------------------------- */
      for( iter = 0; iter < NUM_STEPS; ++iter ){

        /* TAKE A MEASUREMENT: */
        /* ----------------------------- */
           /* meausrement = ... */

        /* PERFORM THE FEEDBACK STEP: */
        /* ----------------------------- */
           status = feedbackStep( measurement );
           
           if (  status )
               mexPrintf("WARNING: QP solver returned the error code: %d \n", status);

           t2 = getTime();
        /* APPLY THE NEW CONTROL IMMEDIATELY TO THE PROCESS: */
        /* ------------------------------------------------- */
           /* send first piece of acadoVariables.u to process; */
           if( VERBOSE ) mexPrintf("=================================================================\n\n" );
           if( VERBOSE ) mexPrintf("   MPC:  Real-Time Iteration %d:  KKT Tolerance = %.3e\n", iter, getKKT() );
           /* if( VERBOSE ) mexPrintf("\n=================================================================\n" );*/

        /* OPTIONAL: SHIFT THE INITIALIZATION: */
        /* ----------------------------------- */
           /* shiftControls( acadoVariables.uRef ); */
           /* shiftStates  ( acadoVariables.xRef ); */

        /* PREPARE NEXT STEP: */
        /* ------------------ */
           /* preparationStep(); */
      }
      /* if( VERBOSE ) mexPrintf("\n\n              END OF THE REAL-TIME LOOP. \n\n\n"); */


   /* GET THE TIME AT THE END OF THE LOOP: */
   /* ---------------------------------------------- */
      real_t t3 = getTime();

    /* if( VERBOSE ) mexPrintf("=================================================================\n\n" ); */
    if( VERBOSE ) mexPrintf("      Preparation step: %.3e s\n", t1-t0 );
    if( VERBOSE ) mexPrintf("      Feedback step:    %.3e s\n", t2-t1 );
    if( VERBOSE ) mexPrintf("\n=================================================================\n" );


   /* PRINT DURATION AND RESULTS: */
   /* -------------------------------------------------------------------------------------------------- */
      if( !VERBOSE )
      mexPrintf("\n\n AVERAGE DURATION OF ONE REAL-TIME ITERATION:   %.3g μs\n\n", 1e6*(t2-t1)/NUM_STEPS );
      
   /* ASSIGN THE STATES AND CONTROLS TO THE OUTPUTS: */
   /* ---------------------------------------- */
    plhs[0] = mxCreateDoubleMatrix(ACADO_N, ACADO_NU, mxREAL);
    dPoutU = mxGetPr(plhs[0]);
    plhs[1] = mxCreateDoubleMatrix(ACADO_N+1, ACADO_NX, mxREAL);
    dPoutX = mxGetPr(plhs[1]);
    plhs[2] = mxCreateDoubleScalar( getKKT() );

    for( j = 0; j < ACADO_N+1; ++j ) {
        for( i = 0; i < ACADO_NX; ++i ) {
            dPoutX[j + i*(ACADO_N+1)] = acadoVariables.x[j*ACADO_NX + i];
        }
    }
    for( j = 0; j < ACADO_N; ++j ) {
        for( i = 0; i < ACADO_NU; ++i ) {
            dPoutU[j + i*ACADO_N] = acadoVariables.u[j*ACADO_NU + i];
        }
    }
}