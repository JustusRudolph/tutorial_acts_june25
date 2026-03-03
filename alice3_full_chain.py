#!/usr/bin/env python3

import os
from datetime import datetime
import shutil
import argparse
import sys
from acts.examples.reconstruction import (
    addSeeding,
    # TruthSeedRanges,
    SeedFinderConfigArg,
    SeedFinderOptionsArg,
    SeedFilterConfigArg,
    SpacePointGridConfigArg,
    SeedingAlgorithmConfigArg,
    SeedingAlgorithm,
    # ParticleSmearingSigmas,
    addCKFTracks,
    addTruthTrackingGsf,
    #    CKFPerformanceConfig,
    TrackSelectorConfig,
    addKalmanTracks,
    # addAmbiguityResolution,
    AmbiguityResolutionConfig,
    CkfConfig,
    addVertexFitting,
    VertexFinder,
    addSpacePointsMaking,  # May 2025
    addHoughVertexFinding,  # May 2025
)

from acts.examples.simulation import (
    addPythia8,
    addGenParticleSelection,
    addSimParticleSelection,
    addFatras,
    addGeant4,
    ParticleSelectorConfig,
    addDigitization,
    addDigiParticleSelection,
)

import pathlib
import acts
import acts.examples
import acts.examples.geant4

# To automatically unzip stuff
from zipfile import ZipFile

# Move it to an utility tool
def unzipFile(zipfile : pathlib.Path):
    if zipfile.exists():
        # unzip
        with ZipFile(zipfile, 'r') as zip_ref:
            zip_ref.extractall(zipfile.parent)
            print(f"Extracted {zipfile}...")
    else:
        raise FileNotFoundError(f"{zipfile} doesn't exist!")




import alice3.performance.generator as alice3_generator
import alice3.performance.writers as alice3_writers
import alice3.performance.seeding as alice3_seeding
import alice3.performance.plotting as alice3_plotting
import alice3.performance.simulation as alice3_simulation

from job_configs import ChainConfig

u = acts.UnitConstants


def getArgumentParser():
    """Get arguments from command line"""
    parser = argparse.ArgumentParser(
        description="Command line arguments for full chain setup"
    )

    ##### General parameters
    parser.add_argument(
        "--nThreads",
        "-nthr",
        dest="nThreads",
        help="Number of threads",
        type=int,
        default=-1
    )
    parser.add_argument(
        "--nEv",
        "-n",
        dest="nEvents",
        help="nEvents",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--out_dir_prefix",
        dest="out_dir_prefix",
        help="Dir for output",
        type=str,
        default="test",
    )

    parser.add_argument(
        "--seed",
        "--randomSeed",
        dest="seed",
        help="seed to use in the random number generator",
        type=int,
        default=42)
    #####
    return parser


def runFullChain(cfg=None, args=None):
    """
    Run the full ALICE3 simulation and reconstruction chain.
    
    Parameters
    ----------
    cfg : ChainConfig.Config
        Configuration object for the chain
    args : argparse.Namespace
        Command line arguments (same format as getArgumentParser().parse_args())
    """
    ## Geometry configuration in case cfg not set
    if (cfg is None):
        cfg = ChainConfig.Config()

    if (args is None):
        parser = getArgumentParser()
        args = parser.parse_args()

    geo_dir = pathlib.Path(os.path.abspath(os.path.dirname(__file__))) / cfg.general.geo_dir
    print("Loading geometry from ... ",str(geo_dir))
    sys.path.insert(0,str(pathlib.Path(geo_dir).resolve()))

    import buildALICE3Geometry

    ##########################
    ##### SOME OTHER PARAMS
    ##########################

    IA_collisionRegion_forSeeds = (
        250 if cfg.seeding.impParForSeeds < 2.0 else 1000
    )  # mm; large values - for V0 daughter reconstruction

    ### output directory
    IA_outputDirName = (
        "output/"
        + args.out_dir_prefix
        + "_nEv"
        + str(args.nEvents)
        + "_PID"
        + str(cfg.particleGun.gunPID)
        + "_nMeasMin"
        + str(cfg.tracking.nMeasurementsMin)
        + "_ckfChi2Meas"
        + str(cfg.tracking.ckfChi2Measurement)
        + "_ckfMeasPerSurf"
        + str(cfg.tracking.ckfMeasPerSurf)
    )

    outputDir = pathlib.Path.cwd() / IA_outputDirName

    if not outputDir.exists():
        outputDir.mkdir(mode=0o777, parents=True, exist_ok=True)

    detector = buildALICE3Geometry.buildALICE3Geometry(
        geo_dir, cfg.general.enableMaterial, False, acts.logging.INFO
    )
    trackingGeometry = detector.trackingGeometry()
    decorators = detector.contextDecorators()

    if cfg.general.fieldMap != "":
        print(">>> !", cfg.general.fieldMap, "field map is used in this sim+rec run.")
        with open(cfg.general.fieldMap) as magFile:  # Checking if it's RZ or XYZ coordinates
            for l in magFile:
                l = l.strip()
                if l.startswith("#"):
                    continue
                while "  " in l:
                    l = l.replace("  ", " ")
                l = l.split(" ")
                if len(l) == 4:
                    field = acts.MagneticFieldMapRz(cfg.general.fieldMap)
                else:
                    field = acts.MagneticFieldMapXyz(cfg.general.fieldMap)
                break
    else:
        print(">>> !Using Constant B-Field")
        field = acts.ConstantBField(acts.Vector3(0.0, 0.0, cfg.general.MF * u.T))

    rnd = acts.examples.RandomNumbers(seed=args.seed)

    # s = acts.examples.Sequencer(events=nEvents, numThreads=-1)
    s = acts.examples.Sequencer(events=args.nEvents, numThreads=args.nThreads)


    if not cfg.pythia.usePythia:
        alice3_generator.addAlice3ParticleGun(s, outputDir=outputDir)
    else:
        s = alice3_generator.addAlice3Pythia8(s, rnd=rnd,
                                              outputDir=outputDir)
            
    addGenParticleSelection(
        s,
        ParticleSelectorConfig(
            eta=(-cfg.detSim.particleSelectionEta, cfg.detSim.particleSelectionEta),
            pt=(0.05 * u.MeV, None),
            removeNeutral=False,
            # rho=(0.0, 24 * u.mm),
            # absZ=(0.0, 1.0 * u.m),
        ),
    )

    if cfg.detSim.simulation == "Fatras":

        addFatras(
            s,
            trackingGeometry,
            field,
            enableInteractions=True,
            rnd=rnd,
            pMin=cfg.detSim.minFatrasPt,  # GeV, May 2025
            outputDirRoot=outputDir,
            logLevel=acts.logging.INFO,
        )
        
    elif cfg.detSim.simulation == "Geant4":


        alice3_gdml = geo_dir / "o2sim_geometry.gdml"
        
        #Check if we need to unzip
        if not alice3_gdml.exists():
            unzipFile(geo_dir / "o2sim_geometry.gdml.zip")
            
            
        gdml_detector = acts.examples.geant4.GdmlDetector(path=str(alice3_gdml))

        addGeant4(
            s,
            gdml_detector,
            trackingGeometry,
            field,
            # materialMappings=["TRK_SI", "Silicon", "Silicon_elm"],
            materialMappings=["TRK_SILICON", "FT3_SILICON", "FT3_Silicon", "TF3_Silicon"],
            # materialMappings=["TRK_SILICON_SENSITIVE"],
            outputDirRoot=outputDir,
            rnd=rnd,
            logLevel=acts.logging.INFO,
            killVolume=trackingGeometry.highestTrackingVolume,
            killAfterTime=40 * u.ns,  # 25 * u.ns,
            recordHitsOfSecondaries=True,  # False,#True, ### IA
            keepParticlesWithoutHits=True,  # True, ### IA
            killSecondaries=False,
        )
        
    # addSimParticleSelection(
    #     s,
    #     ParticleSelectorConfig(
    #         # eta=(-4.1,4.1), pt=(1 * u.MeV, None), removeNeutral=True, # May 2025
    #         hits=(7, None),  # Nov 2025
    #         # rho=(0.0, 24 * u.mm),
    #         # absZ=(0.0, 1.0 * u.m),
    #     ),
    # )


    s = addDigitization(
        s,
        trackingGeometry,
        field,
        digiConfigFile= cfg.general.digi_file,
        outputDirRoot=outputDir,
        rnd=rnd,
        logLevel=acts.logging.INFO,
        # doMerge=True,   ##!! 
    )


    print("PF:: Adding the DigiParticleSelection")
    alice3_simulation.addDigiParticleSelection(
        s,
        ParticleSelectorConfig(
            eta=(-cfg.detSim.particleSelectionEta, cfg.detSim.particleSelectionEta),
            pt=(1 * u.MeV, None), removeNeutral=True,
            hits=(7, None),
            # rho=(0.0, 24 * u.mm),
            # absZ=(0.0, 1.0 * u.m),
        ),
        measurementLayers=cfg.detSim.particleSelectionLayers,
    )

    # s = addHoughVertexFinding(
    #     s,
    #     outputDirRoot=outputDir,
    #     inputSpacePoints=addSpacePointsMaking(
    #         s,
    #         trackingGeometry,
    #         geo_dir / "geoSelectionForSeedingInner_BARREL_LayersOnly.json",
    #         outputName = "spacePointsForHoughVertexing",
    #         logLevel = acts.logging.VERBOSE
    #     ),
    #     logLevel = acts.logging.VERBOSE
    # )


    s = addSeeding(
        s,
        trackingGeometry,
        field,
        SeedFinderConfigArg(
            r=(None, 210 * u.mm),  # iTOF is at 190 mm! if we want it for seeding
            # r=(None, 150 * u.mm),
            # r=(None, 30 * u.mm),
            # deltaR=(1 * u.mm, 120 * u.mm),  # deltaR=(1. * u.mm, 60 * u.mm),
            deltaR=(1 * u.mm, 200 * u.mm),  # deltaR=(1. * u.mm, 60 * u.mm),
            collisionRegion=(
                -IA_collisionRegion_forSeeds * u.mm,
                IA_collisionRegion_forSeeds * u.mm,
            ),
            z=(-1000 * u.mm, 1000 * u.mm),
            maxSeedsPerSpM=cfg.seeding.maxSeedsPerSpM,  # 2 is minimum, >2 is better for Pb-Pb
            sigmaScattering=cfg.seeding.sigmaScattering,
            radLengthPerSeed=cfg.seeding.radLengthPerSeed,
            minPt=cfg.seeding.minSeedPt * u.GeV,
            impactMax=cfg.seeding.impParForSeeds
            * u.mm,  # important! IB vs ML seeds (e.g. 1 mm is ok for IB seeds, 5 mm - for ML seeds)
            cotThetaMax=27.2899,
            seedConfirmation=True,
            centralSeedConfirmationRange=acts.SeedConfirmationRangeConfig(
                zMinSeedConf=-620 * u.mm,
                zMaxSeedConf=620 * u.mm,
                rMaxSeedConf=4.9
                * u.mm,  # 36 * u.mm,  # IA: dramatically affects acceptance at eta ~4. <5 * u.mm  gives best results
                nTopForLargeR=1,  # number of top space points that confirm my seed at larger R, 1 - no confirmation
                nTopForSmallR=2,
            ),
            forwardSeedConfirmationRange=acts.SeedConfirmationRangeConfig(
                zMinSeedConf=-1220 * u.mm,
                zMaxSeedConf=1220 * u.mm,
                rMaxSeedConf=26 * u.mm,  # 15 * u.mm,  #36 * u.mm,
                nTopForLargeR=1,
                nTopForSmallR=2,
            ),
            # skipPreviousTopSP=True,
            useVariableMiddleSPRange=True,
            deltaRMiddleSPRange=(0.2 * u.mm, 1.0 * u.mm),
        ),
        SeedFinderOptionsArg(bFieldInZ=cfg.seeding.bField * u.T, beamPos=(0 * u.mm, 0 * u.mm)),
        SeedFilterConfigArg(
            seedConfirmation=True if cfg.seeding.impParForSeeds < 2.0 else False,  # mm
            # If seedConfirmation is true we classify seeds as "high-quality" seeds.
            # Seeds that are not confirmed as "high-quality" are only selected if no
            # other "high-quality" seed has been found for that inner-middle doublet
            # Maximum number of normal seeds (not classified as "high-quality" seeds)
            # in seed confirmation
            maxSeedsPerSpMConf=cfg.seeding.filter_maxSeedsPerSpMConf,
            maxQualitySeedsPerSpMConf=cfg.seeding.filter_maxQualitySeedsPerSpMConf,
            # Maximum number of "high-quality" seeds for each inner-middle SP-dublet in
            # seed confirmation. If the limit is reached we check if there is a normal
            # quality seed to be replaced
        ),
        SpacePointGridConfigArg(
            # zBinEdges=[
            # -4000.0,
            # -2500.0,
            # -2000.0,
            # -1320.0,
            # -625.0,
            # -350.0,
            # -250.0,
            # 250.0,
            # 350.0,
            # 625.0,
            # 1320.0,
            # 2000.0,
            # 2500.0,
            # 4000.0,
            # ],
            impactMax=1.0 * u.mm,
            phiBinDeflectionCoverage=3,
        ),
        SeedingAlgorithmConfigArg(
            # zBinNeighborsTop=[
            # [0, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 0],
            # ],
            # zBinNeighborsBottom=[
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 1],
            # [0, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # [-1, 0],
            # ],
            # numPhiNeighbors=1,
        ),
        geoSelectionConfigFile=geo_dir / "../seedingConfigurations" / cfg.seeding.seedingLayers,
        seedingAlgorithm = SeedingAlgorithm.GridTriplet if cfg.seeding.seedingAlgo == "GridTriplet" else "TruthSmeared",
        outputDirRoot=outputDir,
        # writeMatchingDetails=cfg.seeding.writeMatchingDetails, TODO: move to own addSeeding
    )


    alice3_writers.addCKFTracks(
        s,
        trackingGeometry,
        field,
        TrackSelectorConfig(pt=(cfg.tracking.minPt * u.MeV, None),
                            nMeasurementsMin=cfg.tracking.nMeasurementsMin,
                            maxHoles=2,
                            maxOutliers=2,
                            maxSharedHits=2),
        CkfConfig(seedDeduplication=True,
                stayOnSeed=True,
                chi2CutOffMeasurement=15.,
                chi2CutOffOutlier=25.,
                numMeasurementsCutOff=cfg.tracking.ckfMeasPerSurf),
        twoWay=cfg.tracking.twoWayCKF,
        outputDirRoot=outputDir,
        writeTrackSummary=cfg.tracking.writeTrackSummary,
        writeTrackStates=False,
        writeMatchingDetails=cfg.tracking.writeMatchingDetails,
        logLevel=acts.logging.INFO
    )

    s = alice3_writers.addAmbiguityResolution(
        s,
        AmbiguityResolutionConfig(
            maximumSharedHits=cfg.tracking.maxSharedHits,
            nMeasurementsMin=cfg.tracking.nMeasurementsMin
        ),
        outputDirRoot=outputDir,
        writeMatchingDetails=cfg.tracking.writeMatchingDetails,
        logLevel=acts.logging.INFO,
    )


    alice3_writers.addIterativeTracking(s,
                                        trackingGeometry=trackingGeometry,
                                        geo_dir=geo_dir,
                                        field=field,
                                        iterations=0,
                                        inputTracks="ckf_tracks",
                                        outputDir=outputDir)

    s = addVertexFitting(
        s,
        field,
        vertexFinder=VertexFinder.AMVF,
        outputDirRoot=outputDir,
        seeder=acts.examples.VertexSeedFinder.AdaptiveGridSeeder,
        useTime=False,  # True,
    )

    s.run()


if __name__ == "__main__":
    parser = getArgumentParser()
    args = parser.parse_args()
    runFullChain(cfg=ChainConfig.Config(), args=args)