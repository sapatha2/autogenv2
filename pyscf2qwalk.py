import sys
import numpy as np
from pyscf import gto,fci, mcscf, scf,pbc
import math
import cmath
import json 
###########################################################
def find_label(sph_label):
  data = sph_label.split( )
  label = data[2].lstrip('0123456789')
  if(label[0]!='g'):
    return label
  elif(len(data)==3):
    return 'gm'+label[2]
  else:
    return 'gp'+data[3] 

#----------------------------------------------
def print_orb(mol,m,f,k=0):
  coeff=np.array(m.mo_coeff)
  print_orb_coeff(mol,coeff,f,k)
    

def mocoeff_project(coeff):
  if not np.iscomplexobj(coeff):
    return coeff
  avgimag=np.mean(np.abs(coeff.imag))
  #print(avgimag)
  if avgimag < 1e-8:
    return coeff.real
  return coeff
#----------------------------------------------

def print_orb_coeff(mol,coeff,f,k=0):
  aos_atom=mol.offset_nr_by_atom()
  if isinstance(mol,pbc.gto.Cell):
    if len(coeff.shape)==4:
      coeff=coeff[:,k,:,:]
    else:
      coeff=coeff[k]
  
  if len(coeff.shape)==3:
    assert coeff.shape[0]==2
    coeff=np.vstack((coeff[0].T,coeff[1].T))
    coeff=coeff.T
  coeff=mocoeff_project(coeff)

  nmo=coeff.shape[1]
  count=0
  for ni in range(nmo):
    for ai,a in enumerate(aos_atom):
      for bi,b in enumerate(range(a[2],a[3])):
        f.write("%i %i %i %i\n"%(ni+1,bi+1,ai+1,count+1))
        count += 1


  count=0
  f.write("COEFFICIENTS\n")

  snorm=1./math.sqrt(4.*math.pi)
  pnorm=math.sqrt(3.)*snorm
  dnorm=math.sqrt(5./4.*math.pi);
  norms={'s':snorm,
         'px':pnorm,
         'py':pnorm,
         'pz':pnorm,
         'dxy':math.sqrt(15)*snorm,
         'dyz':math.sqrt(15)*snorm,
         'dz^2':0.5*math.sqrt(5)*snorm,
         'dxz':math.sqrt(15)*snorm,
         'dx2-y2':0.5*math.sqrt(15)*snorm,
         'fy^3':math.sqrt(35./(32*math.pi)), 
         'fxyz':math.sqrt(105./(4*math.pi)),
         'fyz^2':math.sqrt(21./(32*math.pi)),
         'fz^3':math.sqrt(7./(16*math.pi)),
         'fxz^2':math.sqrt(21./(32*math.pi)),
         'fzx^2':math.sqrt(105./(16.*math.pi)),
         'fx^3':math.sqrt(35./(32*math.pi)),
         'gm4':2.50334294, 
         'gm3':1.77013077, 
         'gm2':0.9461747,
         'gm1':0.6690465425,
         'gp0':0.1057855475, 
         'gp1':0.6690465425,
         'gp2':0.47308735,
         'gp3':1.77013077,
         'gp4':0.62583574}

    #Can get these normalizations using this function.
    #print(gto.mole.cart2sph(3))
    #Translation from pyscf -> qwalk:
    # y^3 -> Fm3, xyz -> Fxyz, fyz^2 -> Fm1, fz^3 -> F0, 
    # fxz^2 -> Fp1, Fxz^2 -> Fp1, Fzx^2 -> Fp2, Fx^3 -> Fp3mod
    # gm4 -> G8, gm3 -> G6, gm2 -> G4, gm1 -> G2, gm0 -> G0, 
    # gp1-> G1, gp2 -> G3, gp3 -> G5, gp4 -> G7
  aosym=[]
  for i in gto.mole.spheric_labels(mol):
    aosym.append(find_label(i))

  for a in coeff.T:
    for ib,b in enumerate(a):
      c=norms[aosym[ib]]*b
      if isinstance(c,float):
        f.write(str(c)+" ")
      else:
        f.write("("+str(c.real)+","+str(c.imag)+") ")
      count+=1
      if count%10==0:
        f.write("\n")

  f.write("\n")
  f.close() 
  return 

###########################################################

def print_basis(mol, f):
  aos_atom= mol.offset_nr_by_atom()
  mom_to_letter ={0:'s', 1:'p', 2:'5D_siesta', 3:'7F_siesta', 4:'9G_pyscf'}
  already_written=[]
  for at, li  in enumerate(aos_atom):
    sym=mol.atom_pure_symbol(at)
    if sym not in already_written:
      already_written.append(sym)
      f.write('''Basis { \n%s  \nAOSPLINE \nGAMESS {\n '''
              %(mol.atom_pure_symbol(at))) 
 
      for bas in range(li[0], li[1]):
        letter=mom_to_letter[mol.bas_angular(bas)]
        ex=mol.bas_exp(bas)
        c=mol.bas_ctr_coeff(bas)

        nrep=len(c[0])
        for r in range(nrep):
        #  letter=mom_to_letter[mol.bas_angular(bas)]
        #  ex=mol.bas_exp(bas)
         # c=mol.bas_ctr_coeff(bas)
  #        if len(c[0]) >1:
  #        print("skipping some coefficients")

          nbas=len(ex)
          f.write("%s  %i\n" %(letter,nbas))

          for i in range(nbas):
            f.write("  %d %f %f \n" %(i+1,ex[i],c[i][r]))
      f.write("}\n }\n")
  f.close() 
  return 


###########################################################
def find_maximal_distance(cell):
  a=cell.lattice_vectors()
  c01=np.cross(a[0],a[1])
  c12=np.cross(a[1],a[2])
  c02=np.cross(a[0],a[2])
  h0=abs(np.dot(a[0],c12)/np.sqrt(np.dot(c12,c12)))
  h1=abs(np.dot(a[1],c02)/np.sqrt(np.dot(c02,c02)))
  h2=abs(np.dot(a[2],c01)/np.sqrt(np.dot(c01,c01)))
  return np.min([h0,h1,h2])/2.00001
###########################################################

def print_sys(mol, f,kpoint=[0.,0.,0.]):
  coords = mol.atom_coords()
  symbols=[]
  charges=[]
  coords_string=[]
    
    # write coordinates
  for i in range(len(coords)):
    symbols.append(mol.atom_pure_symbol(i))
    charges.append(mol.atom_charge(i))
    c = list(map(str, coords[i]))
    coords_string.append(' '.join(c))

  T_charge = sum(charges) + (-mol.charge)
  T_spin = mol.spin

  assert (T_charge+T_spin)%2==0,"""
    Charge and spin should both be even or both be odd.
    mol.spin=%d, mol.charge=%d."""%(mol.spin,mol.charge)

  spin_up =(T_charge + T_spin)//2
  spin_down = (T_charge - T_spin)//2

  if isinstance(mol,pbc.gto.Cell):
    f.write('SYSTEM { PERIODIC \n')
    maxdist=find_maximal_distance(mol)
    ex=[]
    for i in range(mol.nbas):
      ex.extend(mol.bas_exp(i))
    ex=np.min(ex)
    cutoff_length=np.sqrt(-np.log(1e-8)/ex)
    
    f.write('cutoff_divider %g\n'%(maxdist*2.0/cutoff_length))
    f.write('LATTICEVEC {')
    a=mol.lattice_vectors()
    for i in a:
      for j in i:
        f.write(str(j)+" ")
      f.write("\n")
    f.write('}\n')
    f.write("KPOINT { %g %g %g }\n"%tuple(kpoint))
  elif isinstance(mol,gto.Mole):
    f.write('SYSTEM { MOLECULE \n') 
      
  
  f.write('NSPIN { %d  %d }\n' %(spin_up, spin_down))
  for i in range(len(coords)):
    f.write('ATOM { %s  %d  COOR  %s }\n'   %(symbols[i], charges[i], coords_string[i]))


  f.write('}\n')

  if mol.ecp != {}:
    written_out=[]
    for i in range(len(coords)):
      if symbols[i] not in written_out and symbols[i] in mol._ecp.keys():
        written_out.append(symbols[i])
        ecp = mol._ecp[symbols[i]] 
        coeff =ecp[1]
        numofpot =  len(coeff)  
        aip=6
        if numofpot > 2:
          aip=12
        if numofpot > 4:
          aip=18
        f.write('''PSEUDO { \n %s \nAIP %i \nBASIS 
        { \n%s \nRGAUSSIAN \nOLDQMC {\n  ''' 
                %(symbols[i],aip, symbols[i]))
        data=[]     
        N=[]        
        els=[]
        for c in coeff:
          els.append(c[0])
        if -1 in els:
          iteration=list(range(1,len(coeff)))+[0]
        else:
          iteration=range(0,len(coeff))

        for i in iteration:
          eff =coeff[i][1]  
          count=0           
          for j, val in enumerate(eff):
            count+=len(val)
            for v in val:
              data.append([j]+v)
          N.append(str(count))
        
        if -1 not in els: #add a local channel if none given
          data.append([2,1.0,0.0])
          numofpot+=1
          N.append("1")

        f.write("0.0  %d\n" %(numofpot))
        f.write(' '.join(N)+ '\n') 
        for val in data:
          f.write(' '.join(map(str,val)) + '\n')

        f.write(" } \n } \n } \n")
  f.close() 
  return 
###########################################################

def print_slater(mol, mf, orbfile, basisfile, f,k=0,occ=None):
  if occ is None:
    occ=np.array(mf.mo_occ)
  corb = np.array(mf.mo_coeff).flatten()[0]
  if isinstance(mol,pbc.gto.Cell):
    if len(occ.shape)==3:
      occ=occ[:,k,:]
      corb=np.array(mf.mo_coeff)[0,k,:,:]
    else:
      occ=occ[k,:]
      corb=np.array(mf.mo_coeff)[k,:,:]
      
  corb=mocoeff_project(corb)
  
  s=len(occ.shape) 
  tag='RHF'
  if(s==2): 
    tag='UHF'
  
  if np.iscomplexobj(corb):
    orb_type = 'CORBITALS'
  else:
    orb_type = 'ORBITALS'

  te=np.sum(occ)
  ts=mol.spin
  us= (ts+te)/2
  ds= (te-ts)/2
  us_orb=[]
  ds_orb=[]
  max_orb=0
  occup =[ ]
  if(tag == 'UHF'): 
    for i in range(len(occ)):
      temp=[]
      for j, c in enumerate(occ[i]):
        if(c > 0):
          temp += [j+1]
      occup.append(temp)
    us_orb = occup[0]
    ds_orb = list(np.array(occup[1])+len(occ[0]))
  else:  
    for i, c in enumerate(occ):
      if(c>0):
        us_orb.append(i+1)
        c-=1
      if(c>0):
        ds_orb.append(i+1)
  max_orb = np.max(us_orb +ds_orb)
  up_orb=' '.join(list(map(str, us_orb)))
  down_orb= ' '.join(list(map(str, ds_orb)))

  f.write('''SLATER
  %s  { 
  MAGNIFY 1.0 
  NMO %d 
  ORBFILE %s
  INCLUDE %s
  CENTERS { USEGLOBAL }
  }

  DETWT { 1.0 }
  STATES {
  #Spin up orbitals 
  %s 
  #Spin down orbitals 
  %s 
  }''' %(orb_type, max_orb,orbfile, basisfile, up_orb, down_orb ))
  f.close()
  return 

############################################################
def binary_to_occ(S, ncore):
  occup = [ int(i+1) for i in range(ncore)]
  occup += [ int(i+ncore+1)  for i, c in enumerate(reversed(S)) 
          if c=='1']
  max_orb = max(occup) 
  #return  (' '.join([str(a) for a  in occup]), max_orb)
  return (occup, max_orb)
  
  
def print_cas_slater(mc,orbfile, basisfile,f, tol,fjson,root=None):
  norb  = mc.ncas 
  nelec = mc.nelecas
  ncore = mc.ncore 
  orb_cutoff = 0  
    # find multi slater determinant occupation
  detwt = []
  occup = []
  if root==None:
    deters = fci.addons.large_ci(mc.ci, norb, nelec, tol)
  else: 
    deters = fci.addons.large_ci(mc.ci[root], norb, nelec, tol)
     
  for x in deters:
    detwt.append(str(x[0]))
    alpha_occ, alpha_max = binary_to_occ(x[1], ncore)
    beta_occ, beta_max =  binary_to_occ(x[2], ncore)
    orb_cutoff  = max(orb_cutoff, alpha_max, beta_max)
    #tmp= ("# spin up orbitals \n"+ alpha_occ 
    #      + "\n#spin down orbitals \n" + beta_occ) 
    #occup.append(tmp) 
    occup.append((alpha_occ,beta_occ))
    
  json.dump({'detwt':detwt,'occupation':occup},fjson ) 


  det = ' '.join(map(str,detwt))
  occ=""
  for d in occup:
    occ+="#spin up orbitals \n"
    occ+=" ".join(map(str,d[0])) + "\n"
    occ+="#spin down orbitals \n"
    occ+= " ".join(map(str,d[1])) + "\n"
#  occ =  '\n\n'.join(occup) 
    # identify orbital type
  coeff = mc.mo_coeff[0][0] 
  if (isinstance(coeff, np.float64)):
    orb_type = 'ORBITALS'
  else:
    orb_type = 'CORBITALS' 
    
    # write to file
  f.write('''
  SLATER
  %s  { 
  MAGNIFY 1.0 
  NMO %d 
  ORBFILE %s
  INCLUDE %s
  CENTERS { USEATOMS }
  }
  DETWT { %s }
  STATES {
  %s 
  }''' %(orb_type, orb_cutoff, orbfile, basisfile, det, occ))
  f.close()
  return 

###########################################################
def find_basis_cutoff(mol):
  try: 
    return find_maximal_distance(mol)
  except:
    return 7.5 

###########################################################
def find_atom_types(mol):
  atom_types=[]
  n_atom  = len(mol.atom_coords())
  
  for i in range(n_atom):
    atom_types.append(mol.atom_pure_symbol(i))

  return list(set(atom_types))

###########################################################
def print_jastrow(mol,jastfile,optbasis=True,threebody=False):
  
  basis_cutoff = find_basis_cutoff(mol)
  atom_types = find_atom_types(mol)
  
  outlines = [
      "jastrow2",
      "group {",
      ]
  if optbasis: 
    outlines += ['  optimizebasis']
  outlines += [
      "  eebasis {",
      "    ee",
      "    cutoff_cusp",
      "    gamma 24.0",
      "    cusp 1.0",
      "    cutoff {0}".format(basis_cutoff),
      "  }",
      "  eebasis {",
      "    ee",
      "    cutoff_cusp",
      "    gamma 24.0",
      "    cusp 1.0",
      "    cutoff {0}".format(basis_cutoff),
      "  }",
      "  twobody_spin {",
      "    freeze",
      "    like_coefficients { 0.25 0.0 }",
      "    unlike_coefficients { 0.0 0.5 }",
      "  }",
      "}",
      "group {",
      ]
  if optbasis: 
    outlines += ['  optimizebasis']
  for atom_type in atom_types:
    outlines += [
      "  eibasis {",
      "    {0}".format(atom_type),
      "    polypade",
      "    beta0 0.2",
      "    nfunc 4",
      "    rcut {0}".format(basis_cutoff),
      "  }"
    ]
  outlines += [
      "  onebody {",
    ]
  for atom_type in atom_types:
    outlines += [
      "    coefficients {{ {0} 0.0 0.0 0.0 0.0 }}".format(atom_type),
    ]
  outlines += [
      "  }"]
  outlines+=['threebody {',]
  for atom_type in atom_types:
    outlines+=["    coefficients {{ {0} 0. 0. 0. 0.  0. 0. 0. 0.  0. 0. 0. 0.  }}".format(atom_type) ] 
  outlines+=['}']
  outlines+=[
      "  eebasis {",
      "    ee",
      "    polypade",
      "    beta0 0.5",
      "    nfunc 3",
      "    rcut {0}".format(basis_cutoff),
      "  }",
      "  twobody {",
      "    coefficients { 0.0 0.0 0.0 }",
      "  }",
      "}"
  ]

  jastfile.write("\n".join(outlines))

  return None



###########################################################

def print_qwalk_mol(mol, mf, method='scf', tol=0.01, basename='qw'):
  # Some are one-element lists to be compatible with PBC routines.
  files={
      'basis':basename+".basis",
      'jastrow2':basename+".jast2",
      'jastrow3':basename+".jast3",
      'sys':[basename+".sys"],
      'slater':[basename+".slater"],
      'orb':[basename+".orb"]
    }

  print_orb(mol,mf,open(files['orb'][0],'w'))
  print_basis(mol,open(files['basis'],'w'))
  print_sys(mol,open(files['sys'][0],'w'))
  print_jastrow(mol,open(files['jastrow2'],'w'))
  print_jastrow(mol,open(files['jastrow3'],'w'),threebody=True)

  if method == 'scf':
    print_slater(mol,mf,files['orb'][0],files['basis'],open(files['slater'][0],'w'))
  elif method == 'mcscf':
    files['ci']=basename+".ci.json"
    print_cas_slater(mf,files['orb'][0], files['basis'],open(files['slater'][0],'w'), 
                     tol,open(files['ci'],'w'))
  else:
    raise NotImplementedError("Conversion not available yet.")

  return files
###########################################################

def print_qwalk_pbc(cell,mf,method='scf',tol=0.01,basename='qw'):
  files={
      'basis':basename+".basis",
      'jastrow2':basename+".jast2",
      'orb':["%s_%i.orb"%(basename,nk) for nk in range(mf.kpts.shape[0])],
      'sys':["%s_%i.sys"%(basename,nk) for nk in range(mf.kpts.shape[0])],
      'slater':["%s_%i.slater"%(basename,nk) for nk in range(mf.kpts.shape[0])]
    }

  print_basis(cell,open(files['basis'],'w'))
  print_jastrow(cell,open(files['jastrow2'],'w'))
  
  kpoints=cell.get_scaled_kpts(mf.kpts)
  for i in range(mf.kpts.shape[0]):
    print_slater(cell,mf,files['orb'][i],files['basis'],
                 open(files['slater'][i],'w'),k=i)
    print_sys(cell,open(files['sys'][i],'w'),kpoint=2.*kpoints[i,:])
    print_orb(cell,mf,open(files['orb'][i],'w'),k=i)

  return files
  
###########################################################

def print_qwalk(mol,mf,method='scf',tol=0.01,basename='qw'):
  ''' Convenience function for converting any PySCF object. '''
  if isinstance(mol,pbc.gto.Cell):
    return print_qwalk_pbc(mol,mf,method,tol,basename)
  else:
    return print_qwalk_mol(mol,mf,method,tol,basename)
  
###########################################################

def print_qwalk_chkfile(chkfile,method='scf',tol=0.01,basename='qw'):
  ''' Convenience function for converting using only the chkfile.'''
  from pyscf import lib
  import pyscf

  # The Mole object is saved as a string.
  try:
    mol=pbc.gto.cell.loads(lib.chkfile.load(chkfile,'mol'))
  except:
    mol=pyscf.gto.loads(lib.chkfile.load(chkfile,'mol'))

  # This ensures that no extra stuff is enabled by using a proper SCF object.
  class FakeMF:
    def __init__(self,chkfile):
      self.__dict__=lib.chkfile.load(chkfile,'scf')

  mf=FakeMF(chkfile)  
  return print_qwalk(mol,mf,basename=basename)
  
###########################################################

if __name__=='__main__':
  import sys
  assert len(sys.argv)>=2,"""
  Usage: python pyscf2qwalk.py chkfile <basename>"""
  chkfile=sys.argv[1]

  basename='qw'
  if len(sys.argv)>2:
    basename=sys.argv[2]

  print("Files produced:")
  print( print_qwalk_chkfile(chkfile,basename=basename) )
