from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from pymatgen.io.cif import CifParser
from pymatgen.io.xyz import XYZ
from pymatgen.core.periodic_table import Element
from xml.etree.ElementTree import ElementTree
import numpy as np
import os

class CrystalWriter:
  def __init__(self):
    #Geometry input.
    self.struct=None

    #Electron model
    self.spin_polarized=True    
    self.xml_name="BFD_Library.xml"
    self.functional={'exchange':'PBE','correlation':'PBE','hybrid':0,'predefined':None}
    self.total_spin=0

    #Numerical convergence parameters
    self.basis_params=[0.2,2,3]
    self.cutoff=0.2    
    self.kmesh=[8,8,8]
    self.gmesh=16
    self.tolinteg=[8,8,8,8,18]
    self.dftgrid=''
    
    #Memory
    self.biposize=100000000
    self.exchsize=10000000
    
    #SCF convergence parameters
    self.initial_charges={}    
    self.fmixing=80
    self.maxcycle=100
    self.edifftol=8
    self.levshift=[]
    self.broyden=[0.01,60,15]
    self.diis=False
    self.smear=0.0
    self.supercell= [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]  
    

    # Use the new crystal2qmc script. This should change soon!
    self.cryapi=True

    self.restart=False
    self.completed=False
    
  #-----------------------------------------------
    
  def set_struct_fromcif(self,cifstr,primitive=True):
    self.primitive=primitive
    self.cif=cifstr
    self.struct=CifParser.from_string(self.cif).get_structures(primitive=self.primitive)[0].as_dict()
    self.boundary="3d"
  #-----------------------------------------------

  def set_struct_fromxyz(self,xyzstr):
    self.xyz=xyzstr
    self.struct=XYZ.from_string(xyzstr).molecule.as_dict()
    self.boundary="0d"

  #-----------------------------------------------

  def set_options(self, d):
    selfdict=self.__dict__
    for k in d.keys():
      if not k in selfdict.keys():
        print("Error:",k,"not a keyword for CrystalWriter")
        raise AssertionError
      selfdict[k]=d[k]

  #-----------------------------------------------
  def crystal_input(self,section4=[]):

    assert self.struct is not None,'Need to set "struct" first.'
    geomlines=self.geom()
    basislines=self.basis_section()

    modisym=[]
    
    outlines = ["Generated by CrystalWriter"] +\
                geomlines +\
                modisym + \
                ["END"] +\
                basislines +\
                ["99 0"] +\
                ["CHARGED"] +\
                ["END"]

    if self.boundary=="3d": # Can also include 2d later.
      outlines+= ["SHRINK","0 %i"%self.gmesh]
      outlines+= [" ".join(map(str,self.kmesh))]

    outlines+=["DFT"]
    if self.spin_polarized:
      outlines+=["SPIN"]
    if self.functional['predefined']!=None:
      outlines+=[self.functional['predefined']]
    else:
      outlines += [ 
        "EXCHANGE",
        self.functional['exchange'],
        "CORRELAT",
        self.functional['correlation'],
        "HYBRID", 
        str(self.functional['hybrid'])]
    if self.dftgrid!="":
      outlines+=[self.dftgrid]
    outlines+=["END",
      "SCFDIR",
      "BIPOSIZE",
      str(self.biposize),
      "EXCHSIZE",
      str(self.exchsize),
      "TOLDEE",
      str(self.edifftol),
      "FMIXING",
      str(self.fmixing),
      "TOLINTEG",
      ' '.join(map(str,self.tolinteg)),
      "MAXCYCLE",
      str(self.maxcycle),
      "SAVEWF"
    ]
    if self.smear > 0:
      outlines+=["SMEAR",str(self.smear)]
    if self.spin_polarized:
      outlines+=['SPINLOCK',str(self.total_spin)+" 200"]

    if self.diis:
      pass
    elif self.levshift!=[]:
      outlines+=["LEVSHIFT"," ".join(map(str,self.levshift))]
    else:
      outlines+=["BROYDEN"," ".join(map(str,self.broyden))]
    outlines+=section4
    if self.restart:
      outlines+=["GUESSP"]
    outlines+=["END"]

    return "\n".join(outlines)

  #-----------------------------------------------
  def properties_input(self):
    outlines=['NEWK']
    if self.boundary=='3d':
      outlines+=[ "0 %i"%self.gmesh,
                  " ".join(map(str,self.kmesh))]
    outlines+=["1 0"]
    if self.cryapi:
      outlines+=["CRYAPI_OUT"]
    else:
      outlines+=["67 999"]
    outlines+=["END"]
    return "\n".join(outlines)

  #-----------------------------------------------
  def write_crys_input(self,filename):
    outstr=self.crystal_input()
    with open(filename,'w') as outf:
      outf.write(outstr)
      outf.close()
    self.completed=True

  #-----------------------------------------------
  def write_prop_input(self,filename):
    outstr=self.properties_input()
    with open(filename,'w') as outf:
      outf.write(outstr)
    self.completed=True

  #-----------------------------------------------
  def check_status(self):
    # Could add consistancy check here.
    status='unknown'
    if os.path.isfile(self.cryinpfn) and os.path.isfile(self.propinpfn):
      status='ok'
    else:
      status='not_started'
    return status

  #-----------------------------------------------
  def is_consistent(self,other):
    skipkeys = ['completed','biposize','exchsize']
    
    for otherkey in other.__dict__.keys():
      if otherkey not in self.__dict__.keys():
        print('other is missing a key.')
        return False

    for selfkey in self.__dict__.keys():
      if selfkey not in other.__dict__.keys():
        print('self is missing a key.')
        return False

    #Compare the 
    for key in self.__dict__.keys():
      if key in skipkeys:
        equal=True
      else: 
        equal=self.__dict__[key]==other.__dict__[key] 

      if not equal:
        print("Different keys [{}] = \n{}\n or \n{}"\
            .format(key,self.__dict__[key],other.__dict__[key]))
        return False
      
    return True

########################################################
  def geom(self):
    """Generate the geometry section for CRYSTAL"""
    assert self.boundary in ['0d','3d'],"Invalid or not implemented boundary."
    if self.boundary=="3d":
      return self.geom3d()
    elif self.boundary=='0d': 
      return self.geom0d()
    else:
      print("Weird value of self.boundary",self.boundary)
      quit() # This shouldn't happen.

########################################################

  def geom3d(self):
    lat=self.struct['lattice']
    sites=self.struct['sites']
    geomlines=["CRYSTAL","0 0 0","1","%g %g %g %g %g %g"%\
          (lat['a'],lat['b'],lat['c'],lat['alpha'],lat['beta'],lat['gamma'])]

    geomlines+=["%i"%len(sites)]
    for v in sites:
      nm=v['species'][0]['element']
      nm=str(Element(nm).Z+200)
      geomlines+=[nm+" %g %g %g"%(v['abc'][0],v['abc'][1],v['abc'][2])]

    geomlines+=["SUPERCEL"]
    for row in self.supercell:
      geomlines+=[' '.join(map(str,row))]


    return geomlines

########################################################

  def geom0d(self):
    geomlines=["MOLECULE","1"]
    geomlines+=["%i"%len(self.struct['sites'])]
    for v in self.struct['sites']:
      nm=v['species'][0]['element']
      nm=str(Element(nm).Z+200)
      geomlines+=[nm+" %g %g %g"%(v['xyz'][0],v['xyz'][1],v['xyz'][2])]

    return geomlines

########################################################

  def basis_section(self):
    elements=set()
    for s in self.struct['sites']:
      nm=s['species'][0]['element']
      elements.add(nm)
    basislines=[]
    elements = sorted(list(elements)) # Standardize ordering.
    for e in elements:
      basislines+=self.generate_basis(e)
    return basislines


########################################################
  def generate_basis(self,symbol):
    """
    Author: "Kittithat (Mick) Krongchon" <pikkienvd3@gmail.com> and Lucas K. Wagner
    Returns a string containing the basis section.  It is modified according to a simple recipe:
    1) The occupied atomic orbitals are kept, with exponents less than 'cutoff' removed.
    2) These atomic orbitals are augmented with uncontracted orbitals according to the formula 
        e_i = params[0]*params[2]**i, where i goes from 0 to params[1]
        These uncontracted orbitals are added for every occupied atomic orbital (s,p for most elements and s,p,d for transition metals)

    Args:
        symbol (str): The symbol of the element to be specified in the
            D12 file.

    Returns:
        str: The pseudopotential and basis section.


    Uses the following member variables:
        xml_name (str): The name of the XML pseudopotential and basis
            set database.
        cutoff: smallest allowed exponent
        params: parameters for generating the augmenting uncontracted orbitals
        initial_charges    
    """
    
    maxorb=3
    basis_name="vtz"
    nangular={"s":1,"p":1,"d":1,"f":1,"g":0}
    maxcharge={"s":2,"p":6,"d":10,"f":15}
    basis_index={"s":0,"p":2,"d":3,"f":4}
    transition_metals=["Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn"]
    if symbol in transition_metals:
      maxorb=4
      nangular['s']=2
    
    tree = ElementTree()
    tree.parse(self.xml_name)
    element = tree.find('./Pseudopotential[@symbol="{}"]'.format(symbol))
    atom_charge = int(element.find('./Effective_core_charge').text)
    if symbol in self.initial_charges.keys():
      atom_charge-=self.initial_charges[symbol]
    basis_path = './Basis-set[@name="{}"]/Contraction'.format(basis_name)
    found_orbitals = []
    totcharge=0
    ret=[]
    ncontract=0
    for contraction in element.findall(basis_path):
        angular = contraction.get('Angular_momentum')
        if found_orbitals.count(angular) >= nangular[angular]:
            continue

        #Figure out which coefficients to print out based on the minimal exponent
        nterms = 0
        basis_part=[]
        for basis_term in contraction.findall('./Basis-term'):
            exp = basis_term.get('Exp')
            coeff = basis_term.get('Coeff')
            if float(exp) > self.cutoff:
                basis_part += ['  {} {}'.format(exp, coeff)]
                nterms+=1
        #now write the header 
        if nterms > 0:
          found_orbitals.append(angular)          
          charge=min(atom_charge-totcharge,maxcharge[angular])
          #put in a special case for transition metals:
          #depopulate the 4s if the atom is charged
          if symbol in transition_metals and symbol in self.initial_charges.keys() \
                  and self.initial_charges[symbol] > 0 and found_orbitals.count(angular) > 1 \
                  and angular=="s":
            charge=0
          totcharge+=charge
          ret+=["0 %i %i %g 1"%(basis_index[angular],nterms,charge)] + basis_part
          ncontract+=1

    #Add in the uncontracted basis elements
    angular_uncontracted=['s','p']
    if symbol in transition_metals:
        angular_uncontracted.append('d')

    for angular in angular_uncontracted:
        for i in range(0,self.basis_params[1]):
            exp=self.basis_params[0]*self.basis_params[2]**i
            line='{} {}'.format(exp,1.0)
            ret+=["0 %i %i %g 1"%(basis_index[angular],1,0.0),line]
            ncontract+=1

    return ["%i %i"%(Element(symbol).number+200,ncontract)] +\
            self.pseudopotential_section(symbol) +\
            ret
########################################################

  def pseudopotential_section(self,symbol):
    """
    Author: "Kittithat (Mick) Krongchon" <pikkienvd3@gmail.com>
    Returns a string of the pseudopotential section which is to be written
    as part of the basis set section.

    Args:
        symbol (str): The symbol of the element to be specified in the
            D12 file.
        xml_name (str): The name of the XML pseudopotential and basis
            set database.

    Returns:
        list of lines of pseudopotential section (edit by Brian Busemeyer).
    """
    tree = ElementTree()
    tree.parse(self.xml_name)
    element = tree.find('./Pseudopotential[@symbol="{}"]'.format(symbol))
    eff_core_charge = element.find('./Effective_core_charge').text
    local_path = './Gaussian_expansion/Local_component'
    non_local_path = './Gaussian_expansion/Non-local_component'
    local_list = element.findall(local_path)
    non_local_list = element.findall(non_local_path)
    nlocal = len(local_list)
    m = [0, 0, 0, 0, 0]
    proj_path = './Gaussian_expansion/Non-local_component/Proj'
    proj_list = element.findall(proj_path)
    for projector in proj_list:
        m[int(projector.text)] += 1
    strlist = []
    strlist.append('INPUT')
    strlist.append(' '.join(map(str,[eff_core_charge,nlocal,
                                     m[0],m[1],m[2],m[3],m[4]])))
    for local_component in local_list:
        exp_gaus = local_component.find('./Exp').text
        coeff_gaus = local_component.find('./Coeff').text
        r_to_n = local_component.find('./r_to_n').text
        strlist.append(' '.join([exp_gaus, coeff_gaus,r_to_n]))
    for non_local_component in non_local_list:
        exp_gaus = non_local_component.find('./Exp').text
        coeff_gaus = non_local_component.find('./Coeff').text
        r_to_n = non_local_component.find('./r_to_n').text
        strlist.append(' '.join([exp_gaus, coeff_gaus,r_to_n]))
    return strlist
import os 

class CrystalReader:
  """ Tries to extract properties of crystal run, or else diagnose what's wrong. """
  def __init__(self):
    self.completed=False
    self.out={}

    
#-------------------------------------------------      
  def collect(self,outfilename):
    """ Collect results from output."""
    if os.path.isfile(outfilename):
      f = open(outfilename, 'r')
      lines = f.readlines()
      for li,line in enumerate(lines):
        if 'SCF ENDED' in line:
          self.out['total_energy']=float(line.split()[8])    

        elif 'TOTAL ATOMIC SPINS' in line:
          moms = []
          shift = 1
          while "TTT" not in lines[li+shift]:
            moms += map(float,lines[li+shift].split())
            shift += 1
          self.out['mag_moments']=moms
      self.out['etots'] = [float(line.split()[3]) for line in lines if "DETOT" in line]
      
      self.completed=True
    else:
      # Just to be sure/clear...
      self.completed=False


#-------------------------------------------------      
  def write_summary(self):
    print("Crystal total energy",self.out['total_energy'])


#-------------------------------------------------      
  # This can be made more efficient if it's a problem: searches whole file for
  # each query.
  def check_outputfile(self,outfilename,acceptable_scf=10.0):
    """ Check output file. 

    Return values:
    no_record, not_started, ok, too_many_cycles, finished (fall-back),
    scf_fail, not_enough_decrease, divergence, not_finished
    """
    if os.path.isfile(outfilename):
      outf = open(outfilename,'r',errors='ignore')
    else:
      return "not_started"

    outlines = outf.readlines()
    reslines = [line for line in outlines if "ENDED" in line]

    if len(reslines) > 0:
      if "CONVERGENCE" in reslines[0]:
        return "ok"
      elif "TOO MANY CYCLES" in reslines[0]:
        #print("CrystalRunner: Too many cycles.")
        return "too_many_cycles"
      else: # What else can happen?
        #print("CrystalReader: Finished, but unknown state.")
        return "finished"
      
    detots = [float(line.split()[5]) for line in outlines if "DETOT" in line]
    if len(detots) == 0:
      #print("CrystalRunner: Last run completed no cycles.")
      return "scf_fail"

    detots_net = sum(detots[1:])
    if detots_net > acceptable_scf:
      #print("CrystalRunner: Last run performed poorly.")
      return "not_enough_decrease"

    etots = [float(line.split()[3]) for line in outlines if "DETOT" in line]
    if etots[-1] > 0:
      print("CrystalRunner: Energy divergence.")
      return "divergence"
    
    print("CrystalRunner: Not finished.")
    return "not_finished"
  
  
#-------------------------------------------------      
  def status(self,outfilename):
    """ Decide status of crystal run. """

    status=self.check_outputfile(outfilename)
    print("status",status)
    return status
    
