import submission_tools,PropertiesRun,Manager
import CrystalWriter,CrystalRunner,CrystalReader
import local
import os,json


setup={'id':'n2',
        'job_record':submission_tools.JobRecord()
        }
setup['crystal']=CrystalWriter.CrystalWriter(xyz=open("n2.xyz").read())
setup['crystal'].set_options({
    'xml_name':"../BFD_Library.xml",
    'basis_params':[0.2,0,3],
    'cutoff':0.0,
    'dftgrid':'LGRID',
    'spin_polarized':False
  })

testjob = Manager.CrystalManager(
    writer=setup['crystal'],
    reader=CrystalReader.CrystalReader(),
    runner=CrystalRunner.LocalCrystalRunner()
  )

currwd=os.getcwd()
d=setup['id']
try:
  os.mkdir(d)
except:
  pass
os.chdir(d)

testjob.update_status(job_record=setup['job_record'])


